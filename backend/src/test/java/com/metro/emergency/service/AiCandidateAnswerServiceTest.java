package com.metro.emergency.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.repository.PlanRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.doThrow;

class AiCandidateAnswerServiceTest {

    private final WorkflowArtifactRepository artifacts = mock(WorkflowArtifactRepository.class);
    private final PlanRepository plans = mock(PlanRepository.class);
    private final AiCandidateAnswerService service =
            new AiCandidateAnswerService(new ObjectMapper(), artifacts, plans);

    @Test
    void createsStructuredCandidateAndBindsPrePlanEvidence() {
        when(plans.findPlans(null, "二级", "火灾火情事件")).thenReturn(List.of(Map.of(
                "id", 9L, "name", "车站火警预案", "content", "组织疏散", "updateTime", "2026-10-18 10:00:00")));
        when(artifacts.nextAnswerVersion(7L)).thenReturn(1);
        when(artifacts.createWorkflowInstance(anyLong(), anyString(), anyString(), anyInt(), anyString(), any()))
                .thenReturn(11L);
        when(artifacts.insertAnswerCandidate(anyLong(), any(), anyInt(), anyString(), anyString(), anyString(),
                anyString(), any(), any(), any(), any(), any())).thenReturn(12L);

        var result = service.createCandidate(7L, "FIRE", "站台烟雾", "SERIOUS",
                new AiAssessmentService.Assessment("SERIOUS", "存在火灾风险", "RULE_FALLBACK", "1. 组织疏散"), 3L);

        assertTrue(result.persisted());
        assertEquals(1, result.answerVersion());
        verify(artifacts).insertEvidence(anyLong(), anyString(), anyString(), anyString(), anyString(),
                anyString(), anyString(), anyString());
    }

    @Test
    void keepsCandidatePendingWhenKnowledgeEvidenceIsMissing() {
        when(plans.findPlans(null, "三级", "其他突发事件")).thenReturn(List.of());
        when(artifacts.nextAnswerVersion(8L)).thenReturn(1);
        when(artifacts.createWorkflowInstance(anyLong(), anyString(), anyString(), anyInt(), anyString(), any()))
                .thenReturn(21L);
        when(artifacts.insertAnswerCandidate(anyLong(), any(), anyInt(), anyString(), anyString(), anyString(),
                anyString(), any(), any(), any(), any(), any())).thenReturn(22L);

        var result = service.createCandidate(8L, "OTHER", "现场情况待补充", "GENERAL",
                new AiAssessmentService.Assessment("GENERAL", "信息不足", "RULE_FALLBACK", "1. 确认现场"), null);

        assertTrue(result.persisted());
        assertFalse(result.answerId().isBlank());
        verify(artifacts, org.mockito.Mockito.never()).insertEvidence(anyLong(), anyString(), anyString(),
                anyString(), anyString(), anyString(), anyString(), anyString());
    }

    @Test
    void knowledgeStoreFailureDoesNotBlockCandidatePersistence() {
        doThrow(new org.springframework.dao.DataAccessResourceFailureException("database unavailable"))
                .when(plans).findPlans(null, "三级", "其他突发事件");
        when(artifacts.nextAnswerVersion(9L)).thenReturn(1);
        when(artifacts.createWorkflowInstance(anyLong(), anyString(), anyString(), anyInt(), anyString(), any()))
                .thenReturn(31L);
        when(artifacts.insertAnswerCandidate(anyLong(), any(), anyInt(), anyString(), anyString(), anyString(),
                anyString(), any(), any(), any(), any(), any())).thenReturn(32L);

        var result = service.createCandidate(9L, "OTHER", "需要后续核实", "GENERAL",
                new AiAssessmentService.Assessment("GENERAL", "规则降级", "RULE_FALLBACK", "1. 确认现场"), null);

        assertTrue(result.persisted());
        verify(artifacts).insertAnswerCandidate(anyLong(), any(), anyInt(), anyString(), anyString(), anyString(),
                anyString(), any(), any(), any(), any(), any());
    }
}
