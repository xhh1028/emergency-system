package com.metro.emergency.controller;

import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.dto.PersonnelSaveRequest;
import com.metro.emergency.dto.RejectEventRequest;
import com.metro.emergency.dto.ResetPasswordRequest;
import com.metro.emergency.dto.StationDecisionResponse;
import com.metro.emergency.dto.StationEventDecisionRequest;
import com.metro.emergency.dto.TaskBatchRequest;
import com.metro.emergency.dto.TaskBatchResponse;
import com.metro.emergency.service.StationWorkflowService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** 车站事件待办、复核和任务分派接口。 */
@RestController
@RequestMapping("/api/station")
public class StationWorkflowController {

    private final StationWorkflowService service;

    public StationWorkflowController(StationWorkflowService service) {
        this.service = service;
    }

    @GetMapping("/events")
    public ApiResponse<PageResponse<Map<String, Object>>> events(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.events(authorization, status, keyword, page, size));
    }

    @GetMapping("/events/{id}")
    public ApiResponse<Map<String, Object>> eventDetail(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(service.eventDetail(authorization, id));
    }

    @PostMapping("/events/{id}/decision")
    public ApiResponse<StationDecisionResponse> decide(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestBody StationEventDecisionRequest request) {
        return ApiResponse.success(service.decide(authorization, id, request));
    }

    @PostMapping("/events/{id}/reject")
    public ApiResponse<Void> reject(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestBody(required = false) RejectEventRequest request) {
        service.reject(authorization, id, request == null ? null : request.reason());
        return ApiResponse.success(null);
    }

    @GetMapping("/personnel/options")
    public ApiResponse<List<Map<String, Object>>> personnel(
            @RequestHeader("Authorization") String authorization) {
        return ApiResponse.success(service.personnel(authorization));
    }

    @GetMapping("/personnel/posts")
    public ApiResponse<List<Map<String, Object>>> personnelPosts(
            @RequestHeader("Authorization") String authorization) {
        return ApiResponse.success(service.personnelPosts(authorization));
    }

    @PostMapping("/personnel")
    public ApiResponse<Map<String, Object>> createPersonnel(
            @RequestHeader("Authorization") String authorization,
            @RequestBody PersonnelSaveRequest request) {
        return ApiResponse.success(service.createPersonnel(authorization, request));
    }

    @PutMapping("/personnel/{id}")
    public ApiResponse<Map<String, Object>> updatePersonnel(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestBody PersonnelSaveRequest request) {
        return ApiResponse.success(service.updatePersonnel(authorization, id, request));
    }

    @PostMapping("/personnel/{id}/reset-password")
    public ApiResponse<Void> resetPersonnelPassword(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestBody ResetPasswordRequest request) {
        service.resetPersonnelPassword(authorization, id, request);
        return ApiResponse.success(null);
    }

    @GetMapping("/commands")
    public ApiResponse<PageResponse<Map<String, Object>>> commands(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.commands(authorization, status, keyword, page, size));
    }

    @GetMapping("/commands/{id}")
    public ApiResponse<Map<String, Object>> commandDetail(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(service.commandDetail(authorization, id));
    }

    @PostMapping("/commands/{id}/sign")
    public ApiResponse<Map<String, Object>> signCommand(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(service.signCommand(authorization, id));
    }

    @GetMapping("/tasks/progress")
    public ApiResponse<PageResponse<Map<String, Object>>> taskProgress(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) Long eventId,
            @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.taskProgress(authorization, eventId, status, keyword, page, size));
    }

    @GetMapping("/tasks/progress/events")
    public ApiResponse<List<Map<String, Object>>> eventTaskProgress(
            @RequestHeader("Authorization") String authorization) {
        return ApiResponse.success(service.eventTaskProgress(authorization));
    }

    @GetMapping("/tasks/{id}")
    public ApiResponse<Map<String, Object>> taskDetail(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(service.taskDetail(authorization, id));
    }

    @PostMapping("/events/{id}/tasks")
    public ApiResponse<TaskBatchResponse> createTasks(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestBody TaskBatchRequest request) {
        return ApiResponse.success(service.createTasks(authorization, id, request));
    }
}
