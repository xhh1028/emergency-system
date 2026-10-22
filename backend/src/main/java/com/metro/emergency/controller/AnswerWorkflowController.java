package com.metro.emergency.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.dto.AnswerReviewRequest;
import com.metro.emergency.repository.DispatchWorkflowRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import com.metro.emergency.repository.StationWorkflowRepository;
import com.metro.emergency.security.TokenService;
import com.metro.emergency.service.AnswerValidationService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.Set;

/** AI 候选答案的独立校验和人工复核接口。 */
@RestController
@RequestMapping("/api/workflow/answers")
public class AnswerWorkflowController {

    private final AnswerValidationService validationService;
    private final WorkflowArtifactRepository artifacts;
    private final DispatchWorkflowRepository dispatchRepository;
    private final TokenService tokenService;
    private final ObjectMapper objectMapper;
    private final StationWorkflowRepository stationRepository;

    public AnswerWorkflowController(AnswerValidationService validationService,
                                    WorkflowArtifactRepository artifacts,
                                    DispatchWorkflowRepository dispatchRepository,
                                    TokenService tokenService, ObjectMapper objectMapper,
                                    StationWorkflowRepository stationRepository) {
        this.validationService = validationService;
        this.artifacts = artifacts;
        this.dispatchRepository = dispatchRepository;
        this.tokenService = tokenService;
        this.objectMapper = objectMapper;
        this.stationRepository = stationRepository;
    }

    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> detail(@PathVariable long id,
                                                    @RequestHeader("Authorization") String authorization) {
        Map<String, Object> candidate = artifacts.findAnswerCandidate(id);
        if (candidate == null) throw new IllegalArgumentException("候选答案不存在");
        requireEventAccess(authorization, ((Number) candidate.get("eventId")).longValue());
        return ApiResponse.success(candidate);
    }

    @GetMapping("/event/{eventId}/latest")
    public ApiResponse<Map<String, Object>> latest(@PathVariable long eventId,
                                                   @RequestHeader("Authorization") String authorization) {
        requireEventAccess(authorization, eventId);
        return ApiResponse.success(artifacts.findLatestAnswerCandidate(eventId));
    }

    @PostMapping("/{id}/validate")
    public ApiResponse<AnswerValidationService.ValidationResult> validate(
            @PathVariable long id, @RequestHeader("Authorization") String authorization) {
        Map<String, Object> candidate = artifacts.findAnswerCandidate(id);
        if (candidate == null) throw new IllegalArgumentException("候选答案不存在");
        String role = requireEventAccess(authorization, ((Number) candidate.get("eventId")).longValue());
        return ApiResponse.success(validationService.validate(id, role));
    }

    @PostMapping("/{id}/review")
    public ApiResponse<AnswerValidationService.ReviewResult> review(
            @PathVariable long id, @RequestHeader("Authorization") String authorization,
            @RequestBody AnswerReviewRequest request) {
        var identity = tokenService.requireIdentity(authorization);
        Map<String, Object> candidate = artifacts.findAnswerCandidate(id);
        if (candidate == null) throw new IllegalArgumentException("候选答案不存在");
        String role = requireEventAccess(authorization, ((Number) candidate.get("eventId")).longValue());
        String modifiedJson = null;
        if (request != null && request.answer() != null) {
            try {
                modifiedJson = objectMapper.writeValueAsString(request.answer());
            } catch (JsonProcessingException exception) {
                throw new IllegalArgumentException("修改后的答案无法结构化保存", exception);
            }
        }
        return ApiResponse.success(validationService.review(id, identity.userId(), role,
                request == null ? null : request.action(), request == null ? null : request.reason(), modifiedJson));
    }

    private String requireEventAccess(String authorization, long eventId) {
        long userId = tokenService.requireIdentity(authorization).userId();
        String role = dispatchRepository.findRole(userId);
        if (!Set.of("STATION", "DISPATCH", "ADMIN", "SYSTEM_ADMIN").contains(role == null ? "" : role)) {
            throw new IllegalArgumentException("当前账号无权查看或复核候选答案");
        }
        if ("STATION".equals(role)) {
            var scope = stationRepository.findUserScope(userId);
            if (scope == null || scope.stationId() == null
                    || stationRepository.findStationEvent(eventId, scope.stationId()) == null) {
                throw new IllegalArgumentException("只能查看或复核本站事件的答案");
            }
        } else if (dispatchRepository.findEvent(eventId) == null) {
            throw new IllegalArgumentException("事件不存在或不在当前业务范围");
        }
        return role;
    }
}
