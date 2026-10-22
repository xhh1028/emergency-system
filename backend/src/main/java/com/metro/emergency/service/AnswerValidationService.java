package com.metro.emergency.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 独立校验候选答案，并处理授权人员的最终复核。
 * 校验通过前候选答案只能停留在 GENERATED；人工动作会保存前后快照和审计链。
 */
@Service
public class AnswerValidationService {
    private static final String VALIDATOR_VERSION = "answer-validator.v1";
    private static final Set<String> LEVELS = Set.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS");
    private static final Set<String> REVIEW_ROLES = Set.of("STATION", "DISPATCH", "ADMIN", "SYSTEM_ADMIN");
    private static final Set<String> REVIEW_ACTIONS = Set.of("ACCEPTED", "MODIFIED", "REJECTED");

    private final ObjectMapper objectMapper;
    private final WorkflowArtifactRepository artifacts;

    public AnswerValidationService(ObjectMapper objectMapper, WorkflowArtifactRepository artifacts) {
        this.objectMapper = objectMapper;
        this.artifacts = artifacts;
    }

    @Transactional
    public ValidationResult validate(long answerId, String operatorRole) {
        Map<String, Object> candidate = requireCandidate(answerId);
        JsonNode answer = parseAnswer(String.valueOf(candidate.get("answerJson")));
        List<Map<String, Object>> evidence = artifacts.findEvidence(answerId);
        Checks checks = evaluate(answer, evidence, operatorRole);
        String failureReason = String.join("；", checks.failures());
        artifacts.insertValidation(answerId, checks.schema(), checks.evidence(), checks.rule(),
                checks.completeness(), checks.order(), checks.permission(), checks.freshness(),
                checks.finalResult(), failureReason.isBlank() ? null : failureReason, VALIDATOR_VERSION);
        if (checks.passed()) {
            artifacts.updateAnswerStatus(answerId, "VALIDATED");
        }
        return new ValidationResult(answerId, checks.schema(), checks.evidence(), checks.rule(),
                checks.completeness(), checks.order(), checks.permission(), checks.freshness(),
                checks.finalResult(), checks.failures());
    }

    @Transactional
    public ReviewResult review(long answerId, long operatorId, String operatorRole,
                               String action, String reason, String modifiedAnswerJson) {
        Map<String, Object> candidate = requireCandidate(answerId);
        String role = normalizeRole(operatorRole);
        String reviewAction = normalizeAction(action);
        String reviewReason = reason == null ? "" : reason.trim();
        if (!REVIEW_ROLES.contains(role)) {
            throw new IllegalArgumentException("当前账号无权复核候选答案");
        }
        if (reviewReason.isBlank() || reviewReason.length() > 1000) {
            throw new IllegalArgumentException("人工复核必须填写原因（1000字以内）");
        }
        String currentStatus = String.valueOf(candidate.get("status"));
        if (("ACCEPTED".equals(reviewAction) || "MODIFIED".equals(reviewAction))
                && !"VALIDATED".equals(currentStatus)) {
            throw new IllegalStateException("候选答案必须先通过独立校验，才能接受或修改");
        }

        String beforeSnapshot = String.valueOf(candidate.get("answerJson"));
        String afterSnapshot = beforeSnapshot;
        long reviewAnswerId = answerId;
        if ("MODIFIED".equals(reviewAction)) {
            afterSnapshot = requireModifiedAnswer(modifiedAnswerJson);
            JsonNode modified = parseAnswer(afterSnapshot);
            Checks checks = evaluate(modified, artifacts.findEvidence(answerId), role);
            if (!checks.passed()) {
                throw new IllegalArgumentException("修改后的答案未通过独立校验：" + String.join("；", checks.failures()));
            }
            int version = artifacts.nextAnswerVersion(number(candidate.get("eventId")));
            reviewAnswerId = artifacts.insertAnswerCandidate(
                    number(candidate.get("eventId")), numberOrNull(candidate.get("workflowInstanceId")),
                    version, "HUMAN", "MODIFIED", "answer.v1", afterSnapshot,
                    null, null, sha256(afterSnapshot), String.valueOf(candidate.get("knowledgeVersion")), operatorId);
            artifacts.copyEvidence(answerId, reviewAnswerId);
            artifacts.insertValidation(reviewAnswerId, "PASS", "PASS", "PASS", "PASS", "PASS",
                    "PASS", "PASS", "PASS", null, VALIDATOR_VERSION);
            artifacts.updateAnswerStatus(answerId, "MODIFIED");
        } else {
            artifacts.updateAnswerStatus(answerId, reviewAction);
        }

        artifacts.insertApproval(reviewAnswerId, operatorId, role, reviewAction,
                beforeSnapshot, afterSnapshot, reviewReason);
        appendAudit(number(candidate.get("eventId")), numberOrNull(candidate.get("workflowInstanceId")),
                reviewAnswerId, operatorId, reviewAction, beforeSnapshot, afterSnapshot);
        return new ReviewResult(reviewAnswerId, reviewAction, reviewReason, beforeSnapshot, afterSnapshot);
    }

    private Checks evaluate(JsonNode answer, List<Map<String, Object>> evidence, String operatorRole) {
        List<String> failures = new ArrayList<>();
        boolean schema = "answer.v1".equals(answer.path("schemaVersion").asText())
                && answer.path("eventId").canConvertToLong()
                && answer.path("conclusion").isObject()
                && answer.path("actions").isArray()
                && answer.path("validation").isObject()
                && answer.path("decision").isObject();
        if (!schema) failures.add("答案结构不符合 answer.v1 契约");

        Set<String> persistedEvidence = new HashSet<>();
        boolean freshness = !evidence.isEmpty();
        for (Map<String, Object> item : evidence) {
            String key = text(item.get("evidenceKey"));
            persistedEvidence.add(key);
            if (text(item.get("documentVersion")).isBlank() || text(item.get("contentHash")).isBlank()) {
                freshness = false;
            }
        }
        boolean evidencePass = !persistedEvidence.isEmpty();
        for (JsonNode action : answer.path("actions")) {
            JsonNode ids = action.path("evidenceIds");
            if (!ids.isArray() || ids.isEmpty()) evidencePass = false;
            for (JsonNode id : ids) if (!persistedEvidence.contains(id.asText())) evidencePass = false;
        }
        if (!evidencePass) failures.add("动作未绑定可核验的持久化证据");
        if (!freshness) failures.add("证据缺少可确认的知识版本或内容摘要");

        String level = answer.path("conclusion").path("riskLevel").asText("").toUpperCase(Locale.ROOT);
        boolean rule = LEVELS.contains(level);
        if (!rule) failures.add("候选答案等级不在允许范围");

        boolean completeness = !answer.path("conclusion").path("text").asText("").isBlank()
                && answer.path("actions").isArray() && !answer.path("actions").isEmpty()
                && answer.path("missingFacts").isArray() && answer.path("missingFacts").isEmpty();
        if (!completeness) failures.add("答案存在缺失事实或缺少处置动作");

        boolean order = true;
        int expected = 1;
        for (JsonNode action : answer.path("actions")) {
            if (action.path("order").asInt(-1) != expected++) order = false;
            if (action.path("action").asText("").isBlank() || action.path("role").asText("").isBlank()) order = false;
        }
        if (!order) failures.add("处置动作顺序或责任岗位不完整");

        boolean permission = REVIEW_ROLES.contains(normalizeRole(operatorRole));
        if (!permission) failures.add("操作者不具备候选答案复核权限");
        String schemaResult = schema ? "PASS" : "FAIL";
        String evidenceResult = evidencePass ? "PASS" : "FAIL";
        String ruleResult = rule ? "PASS" : "FAIL";
        String completenessResult = completeness ? "PASS" : "FAIL";
        String orderResult = order ? "PASS" : "FAIL";
        String permissionResult = permission ? "PASS" : "FAIL";
        String freshnessResult = freshness ? "PASS" : "FAIL";
        boolean passed = schema && evidencePass && rule && completeness && order && permission && freshness;
        return new Checks(schemaResult, evidenceResult, ruleResult, completenessResult, orderResult,
                permissionResult, freshnessResult, passed ? "PASS" : "FAIL", failures);
    }

    private Map<String, Object> requireCandidate(long answerId) {
        Map<String, Object> candidate = artifacts.findAnswerCandidate(answerId);
        if (candidate == null) throw new IllegalArgumentException("候选答案不存在");
        return candidate;
    }

    private JsonNode parseAnswer(String json) {
        try {
            return objectMapper.readTree(json);
        } catch (JsonProcessingException | IllegalArgumentException exception) {
            throw new IllegalArgumentException("候选答案不是合法 JSON", exception);
        }
    }

    private String requireModifiedAnswer(String json) {
        if (json == null || json.isBlank()) throw new IllegalArgumentException("修改后的答案不能为空");
        return json.trim();
    }

    private void appendAudit(long eventId, Long workflowId, long answerId, long operatorId,
                             String action, String before, String after) {
        String previous = artifacts.findLatestAuditHash(eventId);
        String current = sha256(String.valueOf(previous) + "|" + action + "|" + before + "|" + after);
        artifacts.appendAudit(eventId, workflowId, answerId, "ANSWER_REVIEW", operatorId,
                before, after, previous, current);
    }

    private String normalizeRole(String role) {
        return role == null ? "" : role.trim().toUpperCase(Locale.ROOT);
    }

    private String normalizeAction(String action) {
        String value = action == null ? "" : action.trim().toUpperCase(Locale.ROOT);
        if (!REVIEW_ACTIONS.contains(value)) throw new IllegalArgumentException("人工复核动作不正确");
        return value;
    }

    private long number(Object value) {
        if (value instanceof Number number) return number.longValue();
        return Long.parseLong(String.valueOf(value));
    }

    private Long numberOrNull(Object value) {
        if (value == null) return null;
        return value instanceof Number number ? number.longValue() : Long.valueOf(String.valueOf(value));
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte item : digest) result.append(String.format("%02x", item));
            return result.toString();
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 不可用", exception);
        }
    }

    private record Checks(String schema, String evidence, String rule, String completeness, String order,
                          String permission, String freshness, String finalResult, List<String> failures) {
        boolean passed() { return "PASS".equals(finalResult); }
    }

    public record ValidationResult(long answerId, String schema, String evidence, String rule,
                                   String completeness, String order, String permission, String freshness,
                                   String finalResult, List<String> failures) {
        public boolean passed() { return "PASS".equals(finalResult); }
    }

    public record ReviewResult(long answerId, String action, String reason,
                               String beforeSnapshot, String afterSnapshot) {
    }
}
