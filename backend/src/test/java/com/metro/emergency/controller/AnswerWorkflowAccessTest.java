package com.metro.emergency.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.exception.GlobalExceptionHandler;
import com.metro.emergency.repository.DispatchWorkflowRepository;
import com.metro.emergency.repository.StationWorkflowRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import com.metro.emergency.security.TokenService;
import com.metro.emergency.service.AnswerValidationService;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.http.MediaType;

import java.util.Map;

import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class AnswerWorkflowAccessTest {
    private final WorkflowArtifactRepository artifacts = mock(WorkflowArtifactRepository.class);
    private final DispatchWorkflowRepository dispatch = mock(DispatchWorkflowRepository.class);
    private final StationWorkflowRepository stations = mock(StationWorkflowRepository.class);
    private final AnswerValidationService validation = mock(AnswerValidationService.class);
    private final TokenService tokens = new TokenService();
    private final String auth = "Bearer " + tokens.issue(2L, "reviewer");

    @Test
    void blocksCrossStationReadValidationAndReview() throws Exception {
        when(dispatch.findRole(2L)).thenReturn("STATION");
        when(stations.findUserScope(2L)).thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(artifacts.findAnswerCandidate(42L)).thenReturn(Map.of("eventId", 12L));
        when(stations.findStationEvent(12L, 1L)).thenReturn(null);
        var mvc = mvc();
        mvc.perform(get("/api/workflow/answers/42").header("Authorization", auth))
                .andExpect(jsonPath("$.code").value(400));
        mvc.perform(get("/api/workflow/answers/event/12/latest").header("Authorization", auth))
                .andExpect(jsonPath("$.code").value(400));
        mvc.perform(post("/api/workflow/answers/42/validate").header("Authorization", auth))
                .andExpect(jsonPath("$.code").value(400));
        mvc.perform(post("/api/workflow/answers/42/review").header("Authorization", auth)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"action\":\"ACCEPTED\",\"reason\":\"reviewed\"}"))
                .andExpect(jsonPath("$.code").value(400));
        verifyNoInteractions(validation);
    }

    @Test
    void blocksFrontlineAccessEvenWithValidToken() throws Exception {
        when(dispatch.findRole(2L)).thenReturn("FRONT");
        mvc().perform(get("/api/workflow/answers/event/12/latest").header("Authorization", auth))
                .andExpect(jsonPath("$.code").value(400));
        verifyNoInteractions(artifacts, validation);
    }

    @Test
    void allowsStationToReadItsOwnEventAnswer() throws Exception {
        when(dispatch.findRole(2L)).thenReturn("STATION");
        when(stations.findUserScope(2L)).thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stations.findStationEvent(12L, 1L)).thenReturn(Map.of("id", 12L));
        when(artifacts.findLatestAnswerCandidate(12L)).thenReturn(Map.of("id", 42L));
        mvc().perform(get("/api/workflow/answers/event/12/latest").header("Authorization", auth))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.id").value(42));
    }

    private org.springframework.test.web.servlet.MockMvc mvc() {
        return MockMvcBuilders.standaloneSetup(new AnswerWorkflowController(validation, artifacts, dispatch,
                        tokens, new ObjectMapper(), stations))
                .setControllerAdvice(new GlobalExceptionHandler()).build();
    }
}
