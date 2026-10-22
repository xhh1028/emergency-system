package com.metro.emergency.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AnswerValidationServiceTest {

    private final WorkflowArtifactRepository artifacts = mock(WorkflowArtifactRepository.class);
    private final AnswerValidationService service =
            new AnswerValidationService(new ObjectMapper(), artifacts);

    @Test
    void validatesEvidenceBoundAnswerAndPromotesItToValidated() {
        when(artifacts.findAnswerCandidate(10L)).thenReturn(candidate(10L, 1, "GENERATED", answerJson()));
        when(artifacts.findEvidence(10L)).thenReturn(evidence());

        var result = service.validate(10L, "STATION");

        assertTrue(result.passed());
        verify(artifacts).insertValidation(10L, "PASS", "PASS", "PASS", "PASS", "PASS",
                "PASS", "PASS", "PASS", null, "answer-validator.v1");
        verify(artifacts).updateAnswerStatus(10L, "VALIDATED");
    }

    @Test
    void failsValidationWhenEvidenceIsMissing() {
        when(artifacts.findAnswerCandidate(11L)).thenReturn(candidate(11L, 1, "GENERATED", answerJson()));
        when(artifacts.findEvidence(11L)).thenReturn(List.of());

        var result = service.validate(11L, "STATION");

        assertEquals("FAIL", result.finalResult());
        assertTrue(result.failures().stream().anyMatch(item -> item.contains("证据")));
        org.mockito.Mockito.verify(artifacts, org.mockito.Mockito.never()).updateAnswerStatus(11L, "VALIDATED");
    }

    @Test
    void failsValidationWhenActionOrderIsInvalid() {
        String invalidOrder = answerJson().replace("\"order\":1", "\"order\":2");
        when(artifacts.findAnswerCandidate(16L)).thenReturn(candidate(16L, 1, "GENERATED", invalidOrder));
        when(artifacts.findEvidence(16L)).thenReturn(evidence());

        var result = service.validate(16L, "STATION");

        assertEquals("FAIL", result.finalResult());
        assertEquals("FAIL", result.order());
        org.mockito.Mockito.verify(artifacts, org.mockito.Mockito.never()).updateAnswerStatus(16L, "VALIDATED");
    }

    @Test
    void failsValidationWhenRequiredFactsAreMissing() {
        String incomplete = answerJson().replace("\"missingFacts\":[]", "\"missingFacts\":[\"现场伤亡人数\"]");
        when(artifacts.findAnswerCandidate(17L)).thenReturn(candidate(17L, 1, "GENERATED", incomplete));
        when(artifacts.findEvidence(17L)).thenReturn(evidence());

        var result = service.validate(17L, "STATION");

        assertEquals("FAIL", result.finalResult());
        assertEquals("FAIL", result.completeness());
        org.mockito.Mockito.verify(artifacts, org.mockito.Mockito.never()).updateAnswerStatus(17L, "VALIDATED");
    }

    @Test
    void acceptsValidatedAnswerWithReasonAndAuditSnapshot() {
        when(artifacts.findAnswerCandidate(12L)).thenReturn(candidate(12L, 1, "VALIDATED", answerJson()));
        when(artifacts.findLatestAuditHash(12L)).thenReturn(null);

        var result = service.review(12L, 99L, "DISPATCH", "ACCEPTED", "调度员确认依据充分", null);

        assertEquals("ACCEPTED", result.action());
        verify(artifacts).updateAnswerStatus(12L, "ACCEPTED");
        verify(artifacts).insertApproval(12L, 99L, "DISPATCH", "ACCEPTED", answerJson(), answerJson(), "调度员确认依据充分");
        verify(artifacts).appendAudit(anyLong(), any(), anyLong(), anyString(), any(), anyString(), anyString(), any(), anyString());
    }

    @Test
    void modifiedAnswerCreatesHumanVersionAndRequiresValidReason() {
        String modified = answerJson().replace("组织疏散", "组织分区疏散");
        when(artifacts.findAnswerCandidate(13L)).thenReturn(candidate(13L, 1, "VALIDATED", answerJson()));
        when(artifacts.findEvidence(13L)).thenReturn(evidence());
        when(artifacts.nextAnswerVersion(13L)).thenReturn(2);
        when(artifacts.insertAnswerCandidate(anyLong(), any(), anyInt(), anyString(), anyString(), anyString(),
                anyString(), any(), any(), any(), any(), any())).thenReturn(14L);
        when(artifacts.findLatestAuditHash(13L)).thenReturn(null);

        var result = service.review(13L, 100L, "STATION", "MODIFIED", "补充分区疏散要求", modified);

        assertEquals(14L, result.answerId());
        verify(artifacts).copyEvidence(13L, 14L);
        verify(artifacts).insertValidation(14L, "PASS", "PASS", "PASS", "PASS", "PASS",
                "PASS", "PASS", "PASS", null, "answer-validator.v1");
        verify(artifacts).updateAnswerStatus(13L, "MODIFIED");
        verify(artifacts).insertApproval(14L, 100L, "STATION", "MODIFIED", answerJson(), modified, "补充分区疏散要求");
    }

    @Test
    void rejectsReviewWithoutReason() {
        when(artifacts.findAnswerCandidate(15L)).thenReturn(candidate(15L, 1, "VALIDATED", answerJson()));

        assertThrows(IllegalArgumentException.class,
                () -> service.review(15L, 101L, "STATION", "REJECTED", "", null));
    }

    private Map<String, Object> candidate(long eventId, int version, String status, String json) {
        return Map.of("id", eventId, "eventId", eventId, "workflowInstanceId", 20L,
                "answerVersion", version, "status", status, "answerJson", json,
                "knowledgeVersion", "2026-10-18");
    }

    private List<Map<String, Object>> evidence() {
        return List.of(Map.of("evidenceKey", "pre-plan-9", "documentVersion", "2026-10-18",
                "contentHash", "abc123", "documentId", "pre_plan:9"));
    }

    private String answerJson() {
        return """
                {"schemaVersion":"answer.v1","eventId":10,"answerId":"ans-10",
                 "conclusion":{"riskLevel":"SERIOUS","text":"存在火灾风险"},
                 "actions":[{"order":1,"action":"组织疏散","role":"STATION","mandatory":true,"evidenceIds":["pre-plan-9"]}],
                 "missingFacts":[],"validation":{},"decision":{"status":"PENDING"}}
                """.replaceAll("\\s+", "");
    }
}
