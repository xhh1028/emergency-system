package com.metro.emergency.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.dto.DispatchCloseRequest;
import com.metro.emergency.dto.DispatchCommandRequest;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.dto.TaskEvaluationRequest;
import com.metro.emergency.repository.DispatchWorkflowRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import com.metro.emergency.repository.PlanRepository;
import org.springframework.dao.DuplicateKeyException;
import com.metro.emergency.security.TokenService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.Locale;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** 调度中心接警确认、指令下发、关闭事件和全线任务监督业务。 */
@Service
public class DispatchWorkflowService {
    private final DispatchWorkflowRepository repository;
    private final TokenService tokenService;
    private final RealtimeNotificationService notificationService;
    private final RigidWorkflowRuleService rigidRules;
    private final WorkflowArtifactRepository artifacts;
    private final ObjectMapper objectMapper;
    private final PlanRepository plans;

    public DispatchWorkflowService(DispatchWorkflowRepository repository, TokenService tokenService,
                                   RealtimeNotificationService notificationService,
                                   RigidWorkflowRuleService rigidRules,
                                   WorkflowArtifactRepository artifacts, ObjectMapper objectMapper,
                                   PlanRepository plans) {
        this.repository = repository; this.tokenService = tokenService;
        this.notificationService = notificationService;
        this.rigidRules = rigidRules;
        this.artifacts = artifacts;
        this.objectMapper = objectMapper;
        this.plans = plans;
    }

    public PageResponse<Map<String, Object>> events(String auth, String status, String keyword, int page, int size) {
        requireDispatch(auth); validatePage(page, size);
        return repository.findEvents(status, keyword, page, size);
    }

    public Map<String, Object> eventDetail(String auth, long id) {
        requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        if (event == null) throw new IllegalArgumentException("事件不存在或尚未进入调度范围");
        List<Map<String, Object>> audit = artifacts.findAuditTrail(id);
        event.put("auditTrail", audit);
        event.put("auditChainContinuous", auditChainContinuous(audit));
        event.put("answerHistory", artifacts.findEventAnswerHistory(id));
        return event;
    }

    @Transactional
    public Map<String, Object> confirm(String auth, long id) {
        requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        rigidRules.validateDispatchConfirmation(event);
        if (!Boolean.TRUE.equals(event.get("dispatchConfirmed")) && repository.confirmEvent(id) != 1) {
            throw new IllegalStateException("事件确认失败，请刷新后重试");
        }
        notificationService.publishToStation(((Number) event.get("stationId")).longValue(),
                "事件确认", "调度中心已确认事件", String.valueOf(event.get("eventNo")),
                "/station/progress");
        return repository.findEvent(id);
    }

    @Transactional
    public void sendCommand(String auth, long id, DispatchCommandRequest request) {
        long userId = requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        if (event != null && Boolean.TRUE.equals(event.get("isWithdraw"))) {
            throw new IllegalStateException("已撤回事件不能下发指令");
        }
        RigidWorkflowRuleService.CommandDecision command = rigidRules.validateCommand(event, request);
        String level = command.finalLevel();
        String content = command.content();
        ApprovedAnswer approved = requireApprovedAnswer(id, event, request, level);
        if (repository.existsCommandForAnswer(id, approved.answerId(), approved.answerVersion())) {
            throw new IllegalStateException("该答案版本已经下发过指令，请勿重复下发");
        }
        int inserted;
        try {
            inserted = repository.insertCommand(id, userId, ((Number) event.get("stationId")).longValue(), content,
                approved.answerId(), approved.answerVersion(), approved.validationId(), approved.evidenceSnapshot());
        } catch (DuplicateKeyException exception) {
            throw new IllegalStateException("该答案版本已经下发过指令，请勿重复下发", exception);
        }
        if (inserted != 1 || repository.setFinalLevel(id, level) != 1) {
            throw new IllegalStateException("指令下发失败");
        }
        appendCommandAudit(id, approved, userId, level, content);
        notificationService.publishToStation(((Number) event.get("stationId")).longValue(),
                "新指令", "调度中心下发新指令", content, "/station/commands");
    }

    @Transactional
    public void close(String auth, long id, DispatchCloseRequest request) {
        requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        RigidWorkflowRuleService.CloseDecision close = rigidRules.validateClose(event, request);
        String finalLevel = close.finalLevel();
        if (repository.closeEvent(id, finalLevel) != 1) throw new IllegalStateException("事件关闭失败");
        String requestSnapshot = "finalLevel=" + finalLevel + ",taskCount=" + event.get("taskCount")
                + ",completedCount=" + event.get("completedCount") + ",missingFeedbackCount="
                + event.get("missingFeedbackCount");
        String responseSnapshot = "status=FINISHED,eventNo=" + event.get("eventNo");
        appendAudit(id, null, "EVENT_CLOSE", tokenService.requireIdentity(auth).userId(),
                requestSnapshot, responseSnapshot);
        notificationService.publishAll("事件闭环", "应急事件已关闭",
                String.valueOf(event.get("eventNo")), "/dispatch/archive");
    }

    public PageResponse<Map<String, Object>> progress(String auth, Long stationId, String status,
                                                       String keyword, int page, int size) {
        requireDispatch(auth); validatePage(page, size);
        return repository.findProgress(stationId, status, keyword, page, size);
    }

    public List<Map<String, Object>> stations(String auth) {
        requireDispatch(auth); return repository.findStations();
    }

    @Transactional
    public void evaluateTask(String auth, long taskId, TaskEvaluationRequest request) {
        requireDispatch(auth);
        String evaluation = request == null || request.evaluation() == null
                ? "" : request.evaluation().trim();
        if (evaluation.isBlank() || evaluation.length() > 500) {
            throw new IllegalArgumentException("任务评价不能为空且不能超过500个字符");
        }
        Map<String, Object> task = repository.findProgressTask(taskId);
        if (task == null || !"COMPLETED".equals(task.get("rawStatus"))) {
            throw new IllegalArgumentException("只有已完成任务可以评价");
        }
        if (repository.evaluateTask(taskId, evaluation) != 1) {
            throw new IllegalStateException("任务评价保存失败");
        }
        notificationService.publishToUser(((Number) task.get("executorId")).longValue(),
                "任务评价", "调度中心已评价任务", evaluation, "/field/history");
    }

    public Map<String, Object> overview(String auth) {
        requireDispatch(auth);
        return repository.findOverview();
    }

    public PageResponse<Map<String, Object>> archive(String auth, String keyword, String level,
                                                      Integer year, int page, int size) {
        requireDispatch(auth);
        validatePage(page, size);
        if (level != null && !level.isBlank() && !"ALL".equalsIgnoreCase(level)
                && !isFinalLevel(level)) {
            throw new IllegalArgumentException("归档事件等级不正确");
        }
        if (year != null && (year < 2000 || year > 2100)) {
            throw new IllegalArgumentException("归档年份不正确");
        }
        return repository.findArchive(keyword, level, year, page, size);
    }

    public List<Integer> archiveYears(String auth) {
        requireDispatch(auth);
        return repository.findArchiveYears();
    }

    private long requireDispatch(String auth) {
        long userId = tokenService.requireIdentity(auth).userId();
        if (!"DISPATCH".equalsIgnoreCase(repository.findRole(userId))) {
            throw new IllegalArgumentException("仅调度指挥人员可以执行此操作");
        }
        return userId;
    }

    private boolean isFinalLevel(String value) {
        try {
            rigidRules.normalizeFinalLevel(value);
            return true;
        } catch (IllegalArgumentException ex) {
            return false;
        }
    }

    private void validatePage(int page, int size) {
        if (page < 1 || size < 1 || size > 100) throw new IllegalArgumentException("分页参数不正确");
    }

    private ApprovedAnswer requireApprovedAnswer(long eventId, Map<String, Object> event,
                                                 DispatchCommandRequest request, String finalLevel) {
        if (request == null || request.answerId() == null || request.answerVersion() == null) {
            throw new IllegalArgumentException("下发指令必须指定已批准的答案版本");
        }
        Map<String, Object> candidate = artifacts.findAnswerCandidate(request.answerId());
        if (candidate == null || number(candidate.get("eventId")) != eventId) {
            throw new IllegalArgumentException("答案不存在或不属于当前事件");
        }
        if (number(candidate.get("answerVersion")) != request.answerVersion()) {
            throw new IllegalArgumentException("答案版本不匹配，不能下发");
        }
        Map<String, Object> latestCandidate = artifacts.findLatestAnswerCandidate(eventId);
        if (latestCandidate == null || number(latestCandidate.get("id")) != request.answerId()
                || number(latestCandidate.get("answerVersion")) != request.answerVersion()) {
            throw new IllegalStateException("该答案版本已过期，必须使用最新答案重新完成复核");
        }
        String status = text(candidate.get("status"));
        if (!Set.of("ACCEPTED", "MODIFIED").contains(status)) {
            throw new IllegalStateException("答案尚未完成授权，不能下发指令");
        }
        Map<String, Object> validation = artifacts.findLatestValidation(request.answerId());
        if (validation == null || !"PASS".equals(text(validation.get("finalResult")))
                || !allValidationChecksPass(validation)) {
            throw new IllegalStateException("答案未通过最新独立校验，不能下发指令");
        }
        Map<String, Object> approval = artifacts.findLatestApproval(request.answerId());
        if (approval == null || !status.equals(text(approval.get("action")))
                || text(approval.get("reason")).isBlank()
                || !Set.of("STATION", "DISPATCH", "ADMIN", "SYSTEM_ADMIN").contains(text(approval.get("operatorRole")))
                || !text(candidate.get("answerJson")).equals(text(approval.get("afterSnapshot")))) {
            throw new IllegalStateException("答案缺少与当前版本匹配的人工授权记录");
        }
        List<Map<String, Object>> evidence = artifacts.findEvidence(request.answerId());
        if (evidence.isEmpty() || evidence.stream().anyMatch(item -> text(item.get("documentVersion")).isBlank()
                || text(item.get("contentHash")).isBlank())) {
            throw new IllegalStateException("答案证据不完整或已过期，不能下发指令");
        }
        for (Map<String, Object> item : evidence) validateCurrentEvidence(item);
        String answerLevel = answerRiskLevel(candidate.get("answerJson"));
        if (answerEventId(candidate.get("answerJson")) != eventId) {
            throw new IllegalArgumentException("答案内容中的事件编号与当前事件不一致");
        }
        if (!approvedCommandContent(candidate.get("answerJson")).equals(request.content().trim())) {
            throw new IllegalArgumentException("指令内容必须与批准答案的动作及顺序一致，调整内容请先修改并复核答案");
        }
        if (!compatibleLevel(answerLevel, finalLevel)) {
            throw new IllegalArgumentException("答案建议等级与下发法定等级冲突");
        }
        String recordedLevel = text(event.get("finalLevel")).toUpperCase(Locale.ROOT);
        if (Set.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS").contains(recordedLevel)
                && !recordedLevel.equals(answerLevel)) {
            throw new IllegalArgumentException("批准答案与车站复核等级冲突，请修改答案后重新复核");
        }
        if (Set.of("IV_GENERAL", "III_MAJOR", "II_SERIOUS", "I_EXTREMELY_SERIOUS").contains(recordedLevel)
                && !recordedLevel.equals(finalLevel)) {
            throw new IllegalArgumentException("下发等级与事件已确认等级冲突");
        }
        try {
            return new ApprovedAnswer(request.answerId(), request.answerVersion(),
                    number(validation.get("id")), objectMapper.writeValueAsString(evidence));
        } catch (Exception exception) {
            throw new IllegalStateException("答案证据快照生成失败", exception);
        }
    }

    private boolean allValidationChecksPass(Map<String, Object> validation) {
        return List.of("schemaResult", "evidenceResult", "ruleResult", "completenessResult",
                        "orderResult", "permissionResult", "freshnessResult")
                .stream().allMatch(field -> "PASS".equals(text(validation.get(field))));
    }

    private void validateCurrentEvidence(Map<String, Object> evidence) {
        String documentId = text(evidence.get("documentId"));
        if (!"PRE_PLAN".equals(text(evidence.get("sourceType"))) || !documentId.matches("pre_plan:[0-9]+")) {
            throw new IllegalStateException("证据来源尚无可用的版本核验入口，不能下发指令");
        }
        Map<String, Object> plan = plans.findPlan(Long.parseLong(documentId.substring(9)))
                .orElseThrow(() -> new IllegalStateException("引用预案已不存在，请重新生成并复核答案"));
        if (!text(plan.get("updateTime")).equals(text(evidence.get("documentVersion")))
                || !sha256(text(plan.get("content"))).equals(text(evidence.get("contentHash")))
                || !text(plan.get("content")).equals(text(evidence.get("quote")))) {
            throw new IllegalStateException("引用预案已更新或证据内容不匹配，请重新生成并复核答案");
        }
    }

    private String answerRiskLevel(Object answerJson) {
        try {
            JsonNode root = objectMapper.readTree(text(answerJson));
            String level = root.path("conclusion").path("riskLevel").asText("").trim().toUpperCase(Locale.ROOT);
            if (!Set.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS").contains(level)) {
                throw new IllegalArgumentException("答案缺少有效风险等级");
            }
            return level;
        } catch (IllegalArgumentException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalArgumentException("批准答案不是合法结构化 JSON", exception);
        }
    }

    private long answerEventId(Object answerJson) {
        try {
            JsonNode root = objectMapper.readTree(text(answerJson));
            if (!"answer.v1".equals(root.path("schemaVersion").asText())
                    || !root.path("eventId").canConvertToLong()) {
                throw new IllegalArgumentException("答案缺少有效契约版本或事件编号");
            }
            return root.path("eventId").asLong();
        } catch (IllegalArgumentException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalArgumentException("批准答案不是合法结构化 JSON", exception);
        }
    }

    private String approvedCommandContent(Object answerJson) {
        try {
            JsonNode actions = objectMapper.readTree(text(answerJson)).path("actions");
            if (!actions.isArray() || actions.isEmpty()) throw new IllegalStateException("批准答案缺少处置动作");
            StringBuilder result = new StringBuilder();
            int expected = 1;
            for (JsonNode action : actions) {
                String content = action.path("action").asText("").trim();
                if (action.path("order").asInt() != expected || content.isBlank()) {
                    throw new IllegalStateException("批准答案的动作或顺序无效");
                }
                if (!result.isEmpty()) result.append('\n');
                result.append(expected++).append(". ").append(content);
            }
            return result.toString();
        } catch (com.fasterxml.jackson.core.JsonProcessingException exception) {
            throw new IllegalArgumentException("批准答案不是合法结构化 JSON", exception);
        }
    }

    private boolean compatibleLevel(String answerLevel, String finalLevel) {
        return switch (answerLevel) {
            case "GENERAL" -> "IV_GENERAL".equals(finalLevel) || "III_MAJOR".equals(finalLevel);
            case "SERIOUS" -> "III_MAJOR".equals(finalLevel) || "II_SERIOUS".equals(finalLevel);
            case "EXTREMELY_SERIOUS" -> "II_SERIOUS".equals(finalLevel) || "I_EXTREMELY_SERIOUS".equals(finalLevel);
            default -> false;
        };
    }

    private void appendCommandAudit(long eventId, ApprovedAnswer answer, long operatorId,
                                    String finalLevel, String content) {
        String requestSnapshot = "answerId=" + answer.answerId() + ",answerVersion=" + answer.answerVersion()
                + ",finalLevel=" + finalLevel + ",content=" + content;
        String previous = artifacts.findLatestAuditHash(eventId);
        String current = sha256(String.valueOf(previous) + "|COMMAND_DISPATCH|" + requestSnapshot
                + "|" + answer.evidenceSnapshot());
        artifacts.appendAudit(eventId, null, answer.answerId(), "COMMAND_DISPATCH", operatorId,
                requestSnapshot, answer.evidenceSnapshot(), previous, current);
    }

    private void appendAudit(long eventId, Long answerId, String operation, long operatorId,
                             String requestSnapshot, String responseSnapshot) {
        String previous = artifacts.findLatestAuditHash(eventId);
        String current = sha256(String.valueOf(previous) + "|" + operation + "|" + requestSnapshot
                + "|" + responseSnapshot);
        artifacts.appendAudit(eventId, null, answerId, operation, operatorId,
                requestSnapshot, responseSnapshot, previous, current);
    }

    private boolean auditChainContinuous(List<Map<String, Object>> audit) {
        String previous = null;
        for (Map<String, Object> item : audit) {
            if (!java.util.Objects.equals(previous, item.get("previousHash"))) return false;
            previous = text(item.get("currentHash"));
        }
        return true;
    }

    private String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(64);
            for (byte item : digest) result.append(String.format("%02x", item));
            return result.toString();
        } catch (Exception exception) {
            throw new IllegalStateException("SHA-256 不可用", exception);
        }
    }

    private long number(Object value) {
        if (value instanceof Number number) return number.longValue();
        return Long.parseLong(String.valueOf(value));
    }

    private String text(Object value) { return value == null ? "" : String.valueOf(value); }

    private record ApprovedAnswer(long answerId, int answerVersion, long validationId, String evidenceSnapshot) { }
}
