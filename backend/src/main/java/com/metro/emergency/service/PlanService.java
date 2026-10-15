package com.metro.emergency.service;

import com.metro.emergency.exception.AuthenticationException;
import com.metro.emergency.repository.PlanRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 应急预案查询服务。
 */
@Service
public class PlanService {

    private final PlanRepository planRepository;

    public PlanService(PlanRepository planRepository) {
        this.planRepository = planRepository;
    }

    public List<Map<String, Object>> plans(String keyword, String level, String type) {
        return planRepository.findPlans(keyword, level, type);
    }

    public Map<String, Object> plan(long id) {
        return planRepository.findPlan(id)
                .orElseThrow(() -> new AuthenticationException("预案不存在"));
    }
}
