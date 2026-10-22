package com.metro.emergency.service;

import com.metro.emergency.dto.DispatchCloseRequest;
import com.metro.emergency.dto.DispatchCommandRequest;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Set;

/**
 * 刚性业务流的纯规则闸门。
 *
 * <p>该服务只读取调用方已经加载的事件快照，不执行数据库写入，也不依赖前端输入。
 * 所有失败都返回明确的业务原因，调用方必须在任何写入或通知之前通过对应校验。</p>
 */
@Service
public class RigidWorkflowRuleService {

    private static final Set<String> STATION_LEVELS = Set.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS");
    private static final Set<String> STATION_ROUTES = Set.of("TASK_ASSIGN", "DISPATCH");
    private static final Set<String> FINAL_LEVELS = Set.of(
            "IV_GENERAL", "III_MAJOR", "II_SERIOUS", "I_EXTREMELY_SERIOUS");

    public StationDecision validateStationDecision(Map<String, Object> event, String level, String route) {
        requireEvent(event);
        if (!STATION_LEVELS.contains(level)) {
            throw new IllegalArgumentException("复核等级不正确");
        }
        if (!STATION_ROUTES.contains(route)) {
            throw new IllegalArgumentException("后续处置路径不正确");
        }
        String status = text(event.get("status"));
        if (!Set.of("PENDING", "CONFIRMED").contains(status)) {
            throw new IllegalStateException("当前事件状态不允许定级操作");
        }
        // 严重及以上事件强制进入调度确认；即使调用方传入站内路径，也不能绕过上报。
        boolean reportToDispatch = "SERIOUS".equals(level)
                || "EXTREMELY_SERIOUS".equals(level)
                || "DISPATCH".equals(route);
        return new StationDecision(level, route, reportToDispatch);
    }

    public void validateDispatchConfirmation(Map<String, Object> event) {
        requireEvent(event);
        if (!"REPORTED_TO_DISPATCH".equals(text(event.get("status")))) {
            throw new IllegalArgumentException("只有上报调度的事件可以确认");
        }
    }

    public CommandDecision validateCommand(Map<String, Object> event, DispatchCommandRequest request) {
        requireDispatchEvent(event);
        if (!isTrue(event.get("dispatchConfirmed"))) {
            throw new IllegalArgumentException("请先阅读事件详情并确认已阅");
        }
        String finalLevel = normalizeFinalLevel(request == null ? null : request.finalLevel());
        String content = request == null || request.content() == null ? "" : request.content().trim();
        validateCommandContent(content);
        return new CommandDecision(finalLevel, content);
    }

    public CloseDecision validateClose(Map<String, Object> event, DispatchCloseRequest request) {
        requireEvent(event);
        if ("FINISHED".equals(text(event.get("status")))) {
            throw new IllegalArgumentException("事件不存在或已经关闭");
        }
        int taskCount = number(event.get("taskCount"), "任务统计信息缺失");
        int completed = number(event.get("completedCount"), "任务完成统计信息缺失");
        if (taskCount == 0) {
            throw new IllegalArgumentException("事件尚未生成处置任务，暂不能关闭");
        }
        if (completed < taskCount) {
            throw new IllegalArgumentException("事件仍有未完成任务，暂不能关闭");
        }
        Object missingFeedback = event.get("missingFeedbackCount");
        if (missingFeedback instanceof Number number && number.intValue() > 0) {
            throw new IllegalArgumentException("已完成任务存在缺失现场反馈，暂不能关闭");
        }
        String requested = request == null ? null : request.finalLevel();
        String current = text(event.get("finalLevel"));
        String finalLevel = requested == null || requested.isBlank()
                ? (FINAL_LEVELS.contains(current) ? current : "IV_GENERAL")
                : normalizeFinalLevel(requested);
        return new CloseDecision(finalLevel);
    }

    public String normalizeFinalLevel(String value) {
        String level = value == null ? "" : value.trim().toUpperCase();
        if (!FINAL_LEVELS.contains(level)) {
            throw new IllegalArgumentException("法定事件等级不正确");
        }
        return level;
    }

    public void validateCommandContent(String content) {
        if (content == null || content.isBlank() || content.length() > 2000) {
            throw new IllegalArgumentException("指令内容不能为空且不能超过2000个字符");
        }
    }

    private void requireDispatchEvent(Map<String, Object> event) {
        requireEvent(event);
        if (!"REPORTED_TO_DISPATCH".equals(text(event.get("status")))) {
            throw new IllegalArgumentException("只有上报调度的事件可以下发指令");
        }
    }

    private void requireEvent(Map<String, Object> event) {
        if (event == null) {
            throw new IllegalArgumentException("事件不存在");
        }
    }

    private boolean isTrue(Object value) {
        return Boolean.TRUE.equals(value)
                || (value instanceof Number number && number.intValue() == 1)
                || "true".equalsIgnoreCase(text(value));
    }

    private int number(Object value, String message) {
        if (!(value instanceof Number number)) {
            throw new IllegalStateException(message);
        }
        return number.intValue();
    }

    private String text(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    public record StationDecision(String level, String route, boolean reportToDispatch) {
    }

    public record CommandDecision(String finalLevel, String content) {
    }

    public record CloseDecision(String finalLevel) {
    }
}
