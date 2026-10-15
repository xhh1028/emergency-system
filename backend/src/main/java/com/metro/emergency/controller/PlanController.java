package com.metro.emergency.controller;

import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.service.PlanService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/** 应急预案查询接口，读取 pre_plan 真实数据。 */
@RestController
@RequestMapping("/api/plans")
public class PlanController {

    private final PlanService planService;

    public PlanController(PlanService planService) {
        this.planService = planService;
    }

    @GetMapping
    public ApiResponse<List<Map<String, Object>>> plans(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String level,
            @RequestParam(required = false) String type) {
        return ApiResponse.success(planService.plans(keyword, level, type));
    }

    @GetMapping("/{id}")
    public ApiResponse<Map<String, Object>> plan(
            @RequestHeader("Authorization") String authorization,
            @PathVariable long id) {
        return ApiResponse.success(planService.plan(id));
    }
}
