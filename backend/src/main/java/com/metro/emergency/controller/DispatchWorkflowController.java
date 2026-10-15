package com.metro.emergency.controller;

import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.dto.DispatchCloseRequest;
import com.metro.emergency.dto.DispatchCommandRequest;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.dto.TaskEvaluationRequest;
import com.metro.emergency.service.DispatchWorkflowService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/** 调度指挥端真实事件流转与全线任务监督接口。 */
@RestController
@RequestMapping("/api/dispatch")
public class DispatchWorkflowController {
    private final DispatchWorkflowService service;
    public DispatchWorkflowController(DispatchWorkflowService service) { this.service = service; }

    @GetMapping("/events")
    public ApiResponse<PageResponse<Map<String, Object>>> events(
            @RequestHeader("Authorization") String auth,
            @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.events(auth, status, keyword, page, size));
    }

    @GetMapping("/events/{id}")
    public ApiResponse<Map<String, Object>> detail(@RequestHeader("Authorization") String auth, @PathVariable long id) {
        return ApiResponse.success(service.eventDetail(auth, id));
    }

    @PostMapping("/events/{id}/confirm")
    public ApiResponse<Map<String, Object>> confirm(@RequestHeader("Authorization") String auth, @PathVariable long id) {
        return ApiResponse.success(service.confirm(auth, id));
    }

    @PostMapping("/events/{id}/commands")
    public ApiResponse<Void> command(@RequestHeader("Authorization") String auth, @PathVariable long id,
                                     @RequestBody DispatchCommandRequest request) {
        service.sendCommand(auth, id, request); return ApiResponse.success(null);
    }

    @PostMapping("/events/{id}/close")
    public ApiResponse<Void> close(@RequestHeader("Authorization") String auth, @PathVariable long id,
                                   @RequestBody(required = false) DispatchCloseRequest request) {
        service.close(auth, id, request); return ApiResponse.success(null);
    }

    @GetMapping("/progress")
    public ApiResponse<PageResponse<Map<String, Object>>> progress(
            @RequestHeader("Authorization") String auth,
            @RequestParam(required = false) Long stationId,
            @RequestParam(defaultValue = "ALL") String status,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.progress(auth, stationId, status, keyword, page, size));
    }

    @GetMapping("/stations")
    public ApiResponse<List<Map<String, Object>>> stations(@RequestHeader("Authorization") String auth) {
        return ApiResponse.success(service.stations(auth));
    }

    @PostMapping("/tasks/{id}/evaluation")
    public ApiResponse<Void> evaluateTask(@RequestHeader("Authorization") String auth,
                                          @PathVariable long id,
                                          @RequestBody TaskEvaluationRequest request) {
        service.evaluateTask(auth, id, request);
        return ApiResponse.success(null);
    }

    @GetMapping("/overview")
    public ApiResponse<Map<String, Object>> overview(@RequestHeader("Authorization") String auth) {
        return ApiResponse.success(service.overview(auth));
    }

    @GetMapping("/archive")
    public ApiResponse<PageResponse<Map<String, Object>>> archive(
            @RequestHeader("Authorization") String auth,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "ALL") String level,
            @RequestParam(required = false) Integer year,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.success(service.archive(auth, keyword, level, year, page, size));
    }

    @GetMapping("/archive/years")
    public ApiResponse<List<Integer>> archiveYears(@RequestHeader("Authorization") String auth) {
        return ApiResponse.success(service.archiveYears(auth));
    }
}
