package com.metro.emergency.controller;

import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.dto.EventReportResponse;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.service.EventService;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/** 一线与后勤人员共用的事件上报和个人历史接口。 */
@RestController
@RequestMapping("/api/events")
public class EventController {

    private final EventService eventService;

    public EventController(EventService eventService) {
        this.eventService = eventService;
    }

    @PostMapping(value = "/report", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<EventReportResponse> report(
            @RequestHeader("Authorization") String authorization,
            @RequestParam String eventType,
            @RequestParam(required = false) String preLevel,
            @RequestParam(required = false) Boolean isEmergency,
            @RequestParam(required = false) String eventTitle,
            @RequestParam(required = false) String faultyDevice,
            @RequestParam String description,
            @RequestPart(value = "images", required = false) List<MultipartFile> images) {
        return ApiResponse.success(eventService.report(authorization, eventType, preLevel, eventTitle,
                faultyDevice, description, Boolean.TRUE.equals(isEmergency), images));
    }

    @PostMapping(value = "/{id}/resubmit", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<Map<String, Object>> resubmit(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id,
            @RequestParam(required = false) String eventTitle,
            @RequestParam(required = false) String faultyDevice,
            @RequestParam String description,
            @RequestPart(value = "images", required = false) List<MultipartFile> images) {
        return ApiResponse.success(eventService.resubmit(authorization, id, eventTitle, faultyDevice, description, images));
    }

    @PostMapping("/{id}/withdraw")
    public ApiResponse<Map<String, Object>> withdraw(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(eventService.withdraw(authorization, id));
    }

    @GetMapping("/my-reports")
    public ApiResponse<PageResponse<Map<String, Object>>> myReports(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(
                eventService.myEvents(authorization, keyword, start, end, page, size));
    }

    @GetMapping("/my-completed-tasks")
    public ApiResponse<PageResponse<Map<String, Object>>> completedTasks(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(
                eventService.completedTasks(authorization, keyword, start, end, page, size));
    }
}
