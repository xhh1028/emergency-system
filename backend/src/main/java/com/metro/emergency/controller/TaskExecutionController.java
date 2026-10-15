package com.metro.emergency.controller;

import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.service.TaskExecutionService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;

/** 一线执行与后勤安保人员的本人任务接口。 */
@RestController
@RequestMapping("/api/tasks")
public class TaskExecutionController {

    private final TaskExecutionService service;

    public TaskExecutionController(TaskExecutionService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<PageResponse<Map<String, Object>>> tasks(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.myTasks(authorization, status, keyword, page, size));
    }

    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> detail(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(service.detail(authorization, id));
    }

    @PostMapping("/{id}/start")
    public ApiResponse<Map<String, Object>> start(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(service.start(authorization, id));
    }

    @PostMapping(value = "/{id}/complete", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Map<String, Object>> complete(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestParam String feedbackText,
            @RequestParam(required = false) List<MultipartFile> images) {
        return ApiResponse.success(service.complete(authorization, id, feedbackText, images));
    }
}
