package com.metro.emergency.service;

import com.metro.emergency.dto.DispatchCloseRequest;
import com.metro.emergency.dto.DispatchCommandRequest;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.dto.TaskEvaluationRequest;
import com.metro.emergency.repository.DispatchWorkflowRepository;
import com.metro.emergency.security.TokenService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Set;

/** 调度中心接警确认、指令下发、关闭事件和全线任务监督业务。 */
@Service
public class DispatchWorkflowService {
    private static final Set<String> FINAL_LEVELS = Set.of(
            "IV_GENERAL", "III_MAJOR", "II_SERIOUS", "I_EXTREMELY_SERIOUS");
    private final DispatchWorkflowRepository repository;
    private final TokenService tokenService;
    private final RealtimeNotificationService notificationService;

    public DispatchWorkflowService(DispatchWorkflowRepository repository, TokenService tokenService,
                                   RealtimeNotificationService notificationService) {
        this.repository = repository; this.tokenService = tokenService;
        this.notificationService = notificationService;
    }

    public PageResponse<Map<String, Object>> events(String auth, String status, String keyword, int page, int size) {
        requireDispatch(auth); validatePage(page, size);
        return repository.findEvents(status, keyword, page, size);
    }

    public Map<String, Object> eventDetail(String auth, long id) {
        requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        if (event == null) throw new IllegalArgumentException("事件不存在或尚未进入调度范围");
        return event;
    }

    @Transactional
    public Map<String, Object> confirm(String auth, long id) {
        requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        if (event == null || !"REPORTED_TO_DISPATCH".equals(event.get("status"))) {
            throw new IllegalArgumentException("只有上报调度的事件可以确认");
        }
        if (!Boolean.TRUE.equals(event.get("dispatchConfirmed")) && repository.confirmEvent(id) != 1) {
            throw new IllegalStateException("事件确认失败，请刷新后重试");
        }
        notificationService.publishToStation(((Number) event.get("stationId")).longValue(),
                "事件确认", "调度中心已确认事件", String.valueOf(event.get("eventNo")),
                "/station/progress");
        return repository.findEvent(id);
    }

    @Transactional
    public void sendCommand(String auth, long id, DispatchCommandRequest request) {
        long userId = requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        if (event == null || !"REPORTED_TO_DISPATCH".equals(event.get("status"))) {
            throw new IllegalArgumentException("只有上报调度的事件可以下发指令");
        }
        if (!Boolean.TRUE.equals(event.get("dispatchConfirmed"))) {
            throw new IllegalArgumentException("请先阅读事件详情并确认已阅");
        }
        String level = normalizeFinalLevel(request == null ? null : request.finalLevel());
        String content = request == null || request.content() == null ? "" : request.content().trim();
        if (content.isBlank() || content.length() > 2000) {
            throw new IllegalArgumentException("指令内容不能为空且不能超过2000个字符");
        }
        if (repository.insertCommand(id, userId, ((Number) event.get("stationId")).longValue(), content) != 1
                || repository.setFinalLevel(id, level) != 1) {
            throw new IllegalStateException("指令下发失败");
        }
        notificationService.publishToStation(((Number) event.get("stationId")).longValue(),
                "新指令", "调度中心下发新指令", content, "/station/commands");
    }

    @Transactional
    public void close(String auth, long id, DispatchCloseRequest request) {
        requireDispatch(auth);
        Map<String, Object> event = repository.findEvent(id);
        if (event == null || "FINISHED".equals(event.get("status"))) {
            throw new IllegalArgumentException("事件不存在或已经关闭");
        }
        int taskCount = ((Number) event.get("taskCount")).intValue();
        int completed = ((Number) event.get("completedCount")).intValue();
        if (taskCount == 0) throw new IllegalArgumentException("事件尚未生成处置任务，暂不能关闭");
        if (taskCount > 0 && completed < taskCount) throw new IllegalArgumentException("事件仍有未完成任务，暂不能关闭");
        String requested = request == null ? null : request.finalLevel();
        String current = String.valueOf(event.get("finalLevel"));
        String finalLevel = requested == null || requested.isBlank()
                ? (FINAL_LEVELS.contains(current) ? current : "IV_GENERAL") : normalizeFinalLevel(requested);
        if (repository.closeEvent(id, finalLevel) != 1) throw new IllegalStateException("事件关闭失败");
        notificationService.publishAll("事件闭环", "应急事件已关闭",
                String.valueOf(event.get("eventNo")), "/dispatch/archive");
    }

    public PageResponse<Map<String, Object>> progress(String auth, Long stationId, String status,
                                                       String keyword, int page, int size) {
        requireDispatch(auth); validatePage(page, size);
        return repository.findProgress(stationId, status, keyword, page, size);
    }

    public List<Map<String, Object>> stations(String auth) {
        requireDispatch(auth); return repository.findStations();
    }

    @Transactional
    public void evaluateTask(String auth, long taskId, TaskEvaluationRequest request) {
        requireDispatch(auth);
        String evaluation = request == null || request.evaluation() == null
                ? "" : request.evaluation().trim();
        if (evaluation.isBlank() || evaluation.length() > 500) {
            throw new IllegalArgumentException("任务评价不能为空且不能超过500个字符");
        }
        Map<String, Object> task = repository.findProgressTask(taskId);
        if (task == null || !"COMPLETED".equals(task.get("rawStatus"))) {
            throw new IllegalArgumentException("只有已完成任务可以评价");
        }
        if (repository.evaluateTask(taskId, evaluation) != 1) {
            throw new IllegalStateException("任务评价保存失败");
        }
        notificationService.publishToUser(((Number) task.get("executorId")).longValue(),
                "任务评价", "调度中心已评价任务", evaluation, "/field/history");
    }

    public Map<String, Object> overview(String auth) {
        requireDispatch(auth);
        return repository.findOverview();
    }

    public PageResponse<Map<String, Object>> archive(String auth, String keyword, String level,
                                                      Integer year, int page, int size) {
        requireDispatch(auth);
        validatePage(page, size);
        if (level != null && !level.isBlank() && !"ALL".equalsIgnoreCase(level)
                && !FINAL_LEVELS.contains(level.toUpperCase())) {
            throw new IllegalArgumentException("归档事件等级不正确");
        }
        if (year != null && (year < 2000 || year > 2100)) {
            throw new IllegalArgumentException("归档年份不正确");
        }
        return repository.findArchive(keyword, level, year, page, size);
    }

    public List<Integer> archiveYears(String auth) {
        requireDispatch(auth);
        return repository.findArchiveYears();
    }

    private long requireDispatch(String auth) {
        long userId = tokenService.requireIdentity(auth).userId();
        if (!"DISPATCH".equalsIgnoreCase(repository.findRole(userId))) {
            throw new IllegalArgumentException("仅调度指挥人员可以执行此操作");
        }
        return userId;
    }

    private String normalizeFinalLevel(String value) {
        String level = value == null ? "" : value.toUpperCase();
        if (!FINAL_LEVELS.contains(level)) throw new IllegalArgumentException("法定事件等级不正确");
        return level;
    }

    private void validatePage(int page, int size) {
        if (page < 1 || size < 1 || size > 100) throw new IllegalArgumentException("分页参数不正确");
    }
}
