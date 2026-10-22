package com.metro.emergency.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.repository.PlanRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 把 AI/规则研判结果包装为不可执行的候选答案，并绑定已有预案证据。
 * 候选答案只进入 GENERATED 状态，后续必须经过独立校验和人工决策。
 */
@Service
public class AiCandidateAnswerService {
    private static final Logger log = LoggerFactory.getLogger(AiCandidateAnswerService.class);
    private static final String SCHEMA_VERSION = "answer.v1";

    private final ObjectMapper objectMapper;
    private final WorkflowArtifactRepository artifactRepository;
    private final PlanRepository planRepository;

    public AiCandidateAnswerService(ObjectMapper objectMapper,
                                    WorkflowArtifactRepository artifactRepository,
                                    PlanRepository planRepository) {
        this.objectMapper = objectMapper;
        this.artifactRepository = artifactRepository;
        this.planRepository = planRepository;
    }

    /**
     * 保存候选答案和证据。工作流持久化异常只记录告警，不阻断事件上报主流程。
     * 事件主表中的 AI 研判结果已由调用方单独保存。
     */
    public CandidateResult createCandidate(long eventId, String eventType, String description,
                                           String reporterLevel, AiAssessmentService.Assessment assessment,
                                           Long createdBy) {
        String answerId = "ans-" + UUID.randomUUID();
        String correlationId = "wf-" + UUID.randomUUID();
        List<Map<String, Object>> plans;
        try {
            plans = findEvidence(eventType, assessment.level());
        } catch (DataAccessException exception) {
            // 知识库不可用时仍返回候选编号，但证据留待后续校验；刚性上报不能被 AI 依赖阻断。
            log.warn("知识库查询失败，事件 {} 的候选答案标记为待核验：{}", eventId, exception.getMessage());
            plans = List.of();
        }
        List<String> evidenceIds = plans.stream()
                .map(item -> String.valueOf(item.get("evidenceKey")))
                .toList();
        Map<String, Object> answer = buildAnswer(eventId, answerId, eventType, description,
                reporterLevel, assessment, plans, evidenceIds);
        String answerJson;
        try {
            answerJson = objectMapper.writeValueAsString(answer);
        } catch (JsonProcessingException exception) {
            log.warn("候选答案结构化失败，事件 {} 保留原有 AI 研判：{}", eventId, exception.getMessage());
            return new CandidateResult(null, answerId, "GENERATED", false, 0);
        }

        try {
            int answerVersion = artifactRepository.nextAnswerVersion(eventId);
            long workflowId = artifactRepository.createWorkflowInstance(
                    eventId, "AI_ASSIST", "GENERATED", answerVersion, correlationId, createdBy);
            long candidateId = artifactRepository.insertAnswerCandidate(
                    eventId, workflowId, answerVersion, normalizeSource(assessment.source()), "GENERATED",
                    SCHEMA_VERSION, answerJson, null, null, sha256(answerJson),
                    knowledgeVersion(plans), createdBy);
            for (Map<String, Object> plan : plans) {
                artifactRepository.insertEvidence(candidateId,
                        String.valueOf(plan.get("evidenceKey")), "PRE_PLAN",
                        String.valueOf(plan.get("documentId")),
                        String.valueOf(plan.get("documentVersion")),
                        String.valueOf(plan.get("section")),
                        String.valueOf(plan.get("quote")),
                        sha256(String.valueOf(plan.get("quote"))));
            }
            return new CandidateResult(candidateId, answerId, "GENERATED", true, answerVersion);
        } catch (DataAccessException | IllegalStateException exception) {
            log.warn("候选答案持久化失败，事件 {} 仍保留刚性业务流：{}", eventId, exception.getMessage());
            return new CandidateResult(null, answerId, "GENERATED", false, 0);
        }
    }

    private Map<String, Object> buildAnswer(long eventId, String answerId, String eventType,
                                             String description, String reporterLevel,
                                             AiAssessmentService.Assessment assessment,
                                             List<Map<String, Object>> plans,
                                             List<String> evidenceIds) {
        Map<String, Object> answer = new LinkedHashMap<>();
        answer.put("schemaVersion", SCHEMA_VERSION);
        answer.put("eventId", eventId);
        answer.put("answerId", answerId);
        answer.put("source", normalizeSource(assessment.source()));
        answer.put("generatedAt", LocalDateTime.now().toString());
        answer.put("input", Map.of("eventType", eventType == null ? "" : eventType,
                "reporterLevel", reporterLevel == null ? "" : reporterLevel,
                "description", description == null ? "" : description));
        answer.put("conclusion", Map.of("riskLevel", assessment.level(), "text", assessment.reason()));
        answer.put("actions", actions(assessment.plan(), evidenceIds));
        answer.put("missingFacts", List.of());
        answer.put("assumptions", List.of());
        answer.put("conflicts", List.of());
        answer.put("evidence", plans);
        answer.put("validation", Map.of(
                "schema", "PASS",
                "evidence", plans.isEmpty() ? "PENDING" : "PASS",
                "rule", "PENDING",
                "completeness", "PENDING",
                "order", "PENDING",
                "permission", "PENDING",
                "final", "PENDING"));
        Map<String, Object> decision = new LinkedHashMap<>();
        decision.put("status", "PENDING");
        decision.put("operatorId", null);
        decision.put("reason", null);
        answer.put("decision", decision);
        return answer;
    }

    private List<Map<String, Object>> actions(String plan, List<String> evidenceIds) {
        List<Map<String, Object>> actions = new ArrayList<>();
        String text = plan == null ? "" : plan.trim();
        if (text.isBlank()) return actions;
        int order = 1;
        for (String line : text.split("\\R+")) {
            String action = line.trim().replaceFirst("^\\d+[.、)）]\\s*", "");
            if (action.isBlank()) continue;
            actions.add(Map.of("order", order++, "action", action,
                    "role", "STATION", "mandatory", true, "evidenceIds", evidenceIds));
        }
        return actions;
    }

    private List<Map<String, Object>> findEvidence(String eventType, String level) {
        String type = switch (eventType == null ? "" : eventType) {
            case "DEVICE_FAILURE" -> "设备类故障";
            case "FIRE" -> "火灾火情事件";
            case "PASSENGER" -> "乘客人员事件";
            case "TRACK_OPERATION" -> "轨道异物及行车险情";
            case "CROWD_SECURITY" -> "大客流与治安事件";
            case "DISASTER_ENVIRONMENT" -> "灾害与环境事件";
            default -> "其他突发事件";
        };
        String planLevel = switch (level) {
            case "EXTREMELY_SERIOUS" -> "一级";
            case "SERIOUS" -> "二级";
            default -> "三级";
        };
        List<Map<String, Object>> plans = planRepository.findPlans(null, planLevel, type);
        return plans.stream().map(this::evidenceMap).toList();
    }

    private Map<String, Object> evidenceMap(Map<String, Object> plan) {
        Map<String, Object> evidence = new LinkedHashMap<>();
        String id = String.valueOf(plan.get("id"));
        String quote = String.valueOf(plan.getOrDefault("content", ""));
        evidence.put("evidenceKey", "pre-plan-" + id);
        evidence.put("id", "pre-plan-" + id);
        evidence.put("sourceType", "PRE_PLAN");
        evidence.put("documentId", "pre_plan:" + id);
        evidence.put("documentVersion", String.valueOf(plan.getOrDefault("updateTime", "")));
        evidence.put("section", String.valueOf(plan.getOrDefault("name", "处置预案")));
        evidence.put("quote", quote);
        evidence.put("contentHash", sha256(quote));
        return evidence;
    }

    private String knowledgeVersion(List<Map<String, Object>> plans) {
        return plans.isEmpty() ? null : plans.stream()
                .map(item -> String.valueOf(item.get("documentVersion")))
                .sorted().reduce((first, second) -> second).orElse(null);
    }

    private String normalizeSource(String source) {
        return source != null && source.toUpperCase().startsWith("RULE") ? "RULE" :
                "LLM".equalsIgnoreCase(source) ? "LLM" : "RULE";
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest((value == null ? "" : value).getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte item : digest) result.append(String.format("%02x", item));
            return result.toString();
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 不可用", exception);
        }
    }

    public record CandidateResult(Long candidateId, String answerId, String status,
                                  boolean persisted, int answerVersion) {
    }
}
