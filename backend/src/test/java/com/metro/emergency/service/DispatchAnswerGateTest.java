package com.metro.emergency.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.dto.DispatchCommandRequest;
import com.metro.emergency.dto.DispatchCloseRequest;
import com.metro.emergency.repository.DispatchWorkflowRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import com.metro.emergency.repository.PlanRepository;
import com.metro.emergency.security.TokenService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import com.metro.emergency.controller.DispatchWorkflowController;
import com.metro.emergency.exception.GlobalExceptionHandler;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.dao.DuplicateKeyException;

import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class DispatchAnswerGateTest {
    private final DispatchWorkflowRepository repository = mock(DispatchWorkflowRepository.class);
    private final WorkflowArtifactRepository artifacts = mock(WorkflowArtifactRepository.class);
    private final PlanRepository plans = mock(PlanRepository.class);
    private final TokenService tokens = new TokenService();
    private final RealtimeNotificationService notifications = mock(RealtimeNotificationService.class);
    private final DispatchWorkflowService service = new DispatchWorkflowService(repository, tokens, notifications,
            new RigidWorkflowRuleService(), artifacts, new ObjectMapper(), plans);
    private final String auth = "Bearer " + tokens.issue(7L, "dispatcher");

    @BeforeEach
    void setup() {
        when(repository.findRole(7L)).thenReturn("DISPATCH");
        when(repository.findEvent(12L)).thenReturn(Map.of(
                "id", 12L, "stationId", 3L, "status", "REPORTED_TO_DISPATCH",
                "dispatchConfirmed", true, "eventNo", "EV-12"));
        when(artifacts.findAnswerCandidate(42L)).thenReturn(Map.of(
                "id", 42L, "eventId", 12L, "answerVersion", 3, "status", "ACCEPTED",
                "answerJson", answerJson()));
        when(artifacts.findLatestAnswerCandidate(12L)).thenReturn(Map.of("id", 42L, "answerVersion", 3));
        when(artifacts.findLatestValidation(42L)).thenReturn(validation("PASS"));
        when(artifacts.findLatestApproval(42L)).thenReturn(Map.of(
                "action", "ACCEPTED", "reason", "复核通过", "operatorId", 8L, "operatorRole", "DISPATCH", "afterSnapshot", answerJson()));
        when(artifacts.findEvidence(42L)).thenReturn(List.of(Map.of(
                "documentId", "pre_plan:9", "documentVersion", "2026-10-20",
                "sourceType", "PRE_PLAN", "quote", "plan", "contentHash",
                "64879f7d6b960a01909762d911a32d4582c20010c5641ee90278b644a9e3b525")));
        when(repository.insertCommand(anyLong(), anyLong(), anyLong(), anyString(), anyLong(), anyInt(), anyLong(), anyString()))
                .thenReturn(1);
        when(plans.findPlan(9L)).thenReturn(java.util.Optional.of(Map.of("updateTime", "2026-10-20", "content", "plan")));
        when(repository.setFinalLevel(12L, "II_SERIOUS")).thenReturn(1);
    }

    @Test
    void closeAppendsAuditAfterAllTasksAndFeedbackAreComplete() {
        when(repository.findEvent(12L)).thenReturn(Map.of(
                "id", 12L, "eventNo", "EV-12", "status", "REPORTED_TO_DISPATCH",
                "taskCount", 2, "completedCount", 2, "missingFeedbackCount", 0,
                "finalLevel", "II_SERIOUS"));
        when(repository.closeEvent(12L, "II_SERIOUS")).thenReturn(1);
        when(artifacts.findLatestAuditHash(12L)).thenReturn("prior-hash");

        service.close(auth, 12L, new DispatchCloseRequest(null));

        verify(artifacts).appendAudit(eq(12L), isNull(), isNull(), eq("EVENT_CLOSE"), eq(7L),
                contains("taskCount=2"), contains("status=FINISHED"), eq("prior-hash"), anyString());
    }

    @Test
    void closeDoesNotWriteOrAuditWhenFeedbackIsMissing() {
        when(repository.findEvent(12L)).thenReturn(Map.of(
                "id", 12L, "eventNo", "EV-12", "status", "REPORTED_TO_DISPATCH",
                "taskCount", 2, "completedCount", 2, "missingFeedbackCount", 1,
                "finalLevel", "II_SERIOUS"));

        assertThrows(IllegalArgumentException.class,
                () -> service.close(auth, 12L, new DispatchCloseRequest(null)));

        verify(repository, never()).closeEvent(anyLong(), anyString());
        verify(artifacts, never()).appendAudit(anyLong(), any(), any(), anyString(), any(),
                anyString(), anyString(), any(), any());
    }

    @Test
    void sendsAndAuditsCommandBoundToApprovedAnswerAndEvidence() {
        service.sendCommand(auth, 12L, new DispatchCommandRequest(42L, 3, "II_SERIOUS", "1. 组织现场处置"));

        verify(repository).insertCommand(eq(12L), eq(7L), eq(3L), eq("1. 组织现场处置"),
                eq(42L), eq(3), eq(81L), contains("pre_plan:9"));
        verify(artifacts).appendAudit(eq(12L), isNull(), eq(42L), eq("COMMAND_DISPATCH"), eq(7L),
                anyString(), anyString(), isNull(), anyString());
        verify(notifications).publishToStation(eq(3L), anyString(), anyString(), anyString(), anyString());
    }

    @Test
    void blocksMissingAnswerReference() {
        assertThrows(IllegalArgumentException.class, () -> service.sendCommand(auth, 12L,
                new DispatchCommandRequest("II_SERIOUS", "组织现场处置")));
        verify(repository, never()).insertCommand(anyLong(), anyLong(), anyLong(), anyString(),
                anyLong(), anyInt(), anyLong(), anyString());
    }

    @Test
    void blocksGeneratedOrValidatedButUnapprovedAnswer() {
        when(artifacts.findAnswerCandidate(42L)).thenReturn(Map.of(
                "id", 42L, "eventId", 12L, "answerVersion", 3, "status", "VALIDATED",
                "answerJson", "{\"conclusion\":{\"riskLevel\":\"SERIOUS\"}}"));
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));
        verify(repository, never()).insertCommand(anyLong(), anyLong(), anyLong(), anyString(),
                anyLong(), anyInt(), anyLong(), anyString());
    }

    @Test
    void blocksAnswerForAnotherEventAndStaleVersion() {
        when(artifacts.findAnswerCandidate(42L)).thenReturn(Map.of(
                "id", 42L, "eventId", 99L, "answerVersion", 3, "status", "ACCEPTED",
                "answerJson", answerJson()));
        assertThrows(IllegalArgumentException.class, () -> service.sendCommand(auth, 12L, request()));
        when(artifacts.findAnswerCandidate(42L)).thenReturn(Map.of(
                "id", 42L, "eventId", 12L, "answerVersion", 3, "status", "ACCEPTED",
                "answerJson", answerJson()));
        when(artifacts.findLatestAnswerCandidate(12L)).thenReturn(Map.of("id", 43L, "answerVersion", 4));
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));
        when(artifacts.findLatestAnswerCandidate(12L)).thenReturn(Map.of("id", 42L, "answerVersion", 3));
        when(artifacts.findAnswerCandidate(42L)).thenReturn(Map.of(
                "id", 42L, "eventId", 12L, "answerVersion", 4, "status", "ACCEPTED",
                "answerJson", answerJson()));
        assertThrows(IllegalArgumentException.class, () -> service.sendCommand(auth, 12L, request()));
    }

    @Test
    void blocksFailedValidationStaleEvidenceAndRiskLevelConflict() {
        when(artifacts.findLatestValidation(42L)).thenReturn(validation("FAIL"));
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));

        when(artifacts.findLatestValidation(42L)).thenReturn(validation("PASS"));
        when(artifacts.findEvidence(42L)).thenReturn(List.of(Map.of(
                "documentId", "pre_plan:9", "documentVersion", "", "contentHash", "hash")));
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));

        when(artifacts.findEvidence(42L)).thenReturn(List.of(Map.of(
                "documentId", "pre_plan:9", "documentVersion", "2026-10-20",
                "sourceType", "PRE_PLAN", "quote", "plan", "contentHash",
                "64879f7d6b960a01909762d911a32d4582c20010c5641ee90278b644a9e3b525")));
        assertThrows(IllegalArgumentException.class, () -> service.sendCommand(auth, 12L,
                new DispatchCommandRequest(42L, 3, "IV_GENERAL", "1. 组织现场处置")));
    }

    @Test
    void blocksMissingApprovalAndWithdrawnEvent() {
        when(artifacts.findLatestApproval(42L)).thenReturn(null);
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));
        when(repository.findEvent(12L)).thenReturn(Map.of(
                "id", 12L, "stationId", 3L, "status", "REPORTED_TO_DISPATCH",
                "dispatchConfirmed", true, "eventNo", "EV-12", "isWithdraw", true));
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));
    }

    @Test
    void blocksDuplicateCommandForSameApprovedAnswerVersion() {
        when(repository.existsCommandForAnswer(12L, 42L, 3)).thenReturn(true);
        assertThrows(IllegalStateException.class, () -> service.sendCommand(auth, 12L, request()));
        verify(repository, never()).insertCommand(anyLong(), anyLong(), anyLong(), anyString(),
                anyLong(), anyInt(), anyLong(), anyString());
    }

    @Test
    void apiSendsHumanModifiedAnswerWithItsOwnEvidenceAndValidation() throws Exception {
        Map<String, Object> candidate = new LinkedHashMap<>(artifacts.findAnswerCandidate(42L));
        candidate.put("status", "MODIFIED");
        when(artifacts.findAnswerCandidate(42L)).thenReturn(candidate);
        Map<String, Object> approval = new LinkedHashMap<>(artifacts.findLatestApproval(42L));
        approval.put("action", "MODIFIED");
        when(artifacts.findLatestApproval(42L)).thenReturn(approval);

        performCommand(request(), 200);

        verify(repository).insertCommand(eq(12L), eq(7L), eq(3L), eq("1. 组织现场处置"),
                eq(42L), eq(3), eq(81L), contains("pre_plan:9"));
        verify(artifacts).appendAudit(eq(12L), isNull(), eq(42L), eq("COMMAND_DISPATCH"), eq(7L),
                anyString(), anyString(), isNull(), anyString());
    }

    @ParameterizedTest(name = "API blocks {0} without command/audit/notification")
    @ValueSource(strings = {"MISSING_REFERENCE", "GENERATED", "UNAPPROVED", "STALE_VERSION", "CROSS_EVENT",
            "FAILED_VALIDATION", "MISSING_VALIDATION", "SUBCHECK_FAILED", "MISSING_APPROVAL", "BAD_REVIEW_ROLE",
            "BAD_APPROVAL_SNAPSHOT", "MISSING_EVIDENCE", "UPDATED_PREPLAN", "DELETED_PREPLAN", "WRONG_LEVEL",
            "EVENT_LEVEL_CONFLICT", "TAMPERED_CONTENT", "WITHDRAWN", "UNCONFIRMED", "WRONG_ROLE", "DUPLICATE",
            "JSON_EVENT_CHANGED", "NO_SUCH_ANSWER", "STATION_LEVEL_CONFLICT"})
    void apiBlocksBypassAttempts(String scenario) throws Exception {
        var candidate = new LinkedHashMap<>(artifacts.findAnswerCandidate(42L));
        var event = new LinkedHashMap<>(repository.findEvent(12L));
        var approval = new LinkedHashMap<>(artifacts.findLatestApproval(42L));
        var checks = new LinkedHashMap<>(validation("PASS"));
        var request = request();
        switch (scenario) {
            case "MISSING_REFERENCE" -> request = new DispatchCommandRequest("II_SERIOUS", "1. 组织现场处置");
            case "GENERATED" -> candidate.put("status", "GENERATED");
            case "UNAPPROVED" -> candidate.put("status", "VALIDATED");
            case "STALE_VERSION" -> when(artifacts.findLatestAnswerCandidate(12L)).thenReturn(Map.of("id", 43L, "answerVersion", 4));
            case "CROSS_EVENT" -> candidate.put("eventId", 99L);
            case "FAILED_VALIDATION" -> checks.put("finalResult", "FAIL");
            case "MISSING_VALIDATION" -> when(artifacts.findLatestValidation(42L)).thenReturn(null);
            case "SUBCHECK_FAILED" -> checks.put("evidenceResult", "FAIL");
            case "MISSING_APPROVAL" -> when(artifacts.findLatestApproval(42L)).thenReturn(null);
            case "BAD_REVIEW_ROLE" -> approval.put("operatorRole", "FRONT");
            case "BAD_APPROVAL_SNAPSHOT" -> approval.put("afterSnapshot", "{}");
            case "MISSING_EVIDENCE" -> when(artifacts.findEvidence(42L)).thenReturn(List.of());
            case "UPDATED_PREPLAN" -> when(plans.findPlan(9L)).thenReturn(java.util.Optional.of(Map.of(
                    "updateTime", "2026-10-21", "content", "updated")));
            case "DELETED_PREPLAN" -> when(plans.findPlan(9L)).thenReturn(java.util.Optional.empty());
            case "WRONG_LEVEL" -> request = new DispatchCommandRequest(42L, 3, "IV_GENERAL", "1. 组织现场处置");
            case "EVENT_LEVEL_CONFLICT" -> event.put("finalLevel", "III_MAJOR");
            case "STATION_LEVEL_CONFLICT" -> event.put("finalLevel", "EXTREMELY_SERIOUS");
            case "TAMPERED_CONTENT" -> request = new DispatchCommandRequest(42L, 3, "II_SERIOUS", "擅自增加未经审批动作");
            case "WITHDRAWN" -> event.put("isWithdraw", true);
            case "UNCONFIRMED" -> event.put("dispatchConfirmed", false);
            case "WRONG_ROLE" -> when(repository.findRole(7L)).thenReturn("STATION");
            case "DUPLICATE" -> when(repository.existsCommandForAnswer(12L, 42L, 3)).thenReturn(true);
            case "JSON_EVENT_CHANGED" -> {
                candidate.put("answerJson", answerJson().replace("\"eventId\":12", "\"eventId\":99"));
                approval.put("afterSnapshot", candidate.get("answerJson"));
            }
            case "NO_SUCH_ANSWER" -> when(artifacts.findAnswerCandidate(42L)).thenReturn(null);
            default -> throw new AssertionError(scenario);
        }
        if (!"NO_SUCH_ANSWER".equals(scenario)) when(artifacts.findAnswerCandidate(42L)).thenReturn(candidate);
        if (!"MISSING_APPROVAL".equals(scenario)) when(artifacts.findLatestApproval(42L)).thenReturn(approval);
        if (!"MISSING_VALIDATION".equals(scenario)) when(artifacts.findLatestValidation(42L)).thenReturn(checks);
        when(repository.findEvent(12L)).thenReturn(event);

        performCommand(request, 400);

        verify(repository, never()).insertCommand(anyLong(), anyLong(), anyLong(), anyString(),
                anyLong(), anyInt(), anyLong(), anyString());
        verify(repository, never()).setFinalLevel(anyLong(), anyString());
        verify(artifacts, never()).appendAudit(anyLong(), any(), any(), anyString(), any(), anyString(), anyString(), any(), anyString());
        verifyNoInteractions(notifications);
    }

    @Test
    void apiHandlesDatabaseDuplicateFromConcurrentSubmission() throws Exception {
        when(repository.insertCommand(anyLong(), anyLong(), anyLong(), anyString(), anyLong(), anyInt(), anyLong(), anyString()))
                .thenThrow(new DuplicateKeyException("unique answer version"));
        performCommand(request(), 400);
        verify(repository, never()).setFinalLevel(anyLong(), anyString());
        verifyNoInteractions(notifications);
    }

    private void performCommand(DispatchCommandRequest request, int expectedCode) throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(new DispatchWorkflowController(service))
                .setControllerAdvice(new GlobalExceptionHandler()).build();
        mvc.perform(post("/api/dispatch/events/12/commands").header("Authorization", auth)
                        .contentType(MediaType.APPLICATION_JSON).content(new ObjectMapper().writeValueAsString(request)))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(expectedCode));
    }

    private DispatchCommandRequest request() {
        return new DispatchCommandRequest(42L, 3, "II_SERIOUS", "1. 组织现场处置");
    }

    private String answerJson() {
        return """
                {"schemaVersion":"answer.v1","eventId":12,"conclusion":{"riskLevel":"SERIOUS"},
                 "actions":[{"order":1,"action":"组织现场处置"}]}
                """;
    }

    private Map<String, Object> validation(String finalResult) {
        return Map.of("id", 81L, "finalResult", finalResult,
                "schemaResult", "PASS", "evidenceResult", "PASS", "ruleResult", "PASS",
                "completenessResult", "PASS", "orderResult", "PASS", "permissionResult", "PASS",
                "freshnessResult", "PASS");
    }
}
