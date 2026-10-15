package com.metro.emergency.service;

import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.repository.TaskExecutionRepository;
import com.metro.emergency.security.TokenService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;
import java.util.Set;

/** 一线执行与后勤安保人员共用的任务执行业务。 */
@Service
public class TaskExecutionService {

    private static final Set<String> STATUSES = Set.of(
            "ALL", "PENDING", "IN_PROGRESS", "COMPLETED", "OVERDUE");
    private final TaskExecutionRepository repository;
    private final TokenService tokenService;
    private final ImageStorageService imageStorageService;
    private final RealtimeNotificationService notificationService;

    public TaskExecutionService(TaskExecutionRepository repository, TokenService tokenService,
                                ImageStorageService imageStorageService,
                                RealtimeNotificationService notificationService) {
        this.repository = repository;
        this.tokenService = tokenService;
        this.imageStorageService = imageStorageService;
        this.notificationService = notificationService;
    }

    public PageResponse<Map<String, Object>> myTasks(String authorization, String status,
                                                      String keyword, int page, int size) {
        validatePage(page, size);
        String normalizedStatus = status == null || status.isBlank() ? "ALL" : status.toUpperCase();
        if (!STATUSES.contains(normalizedStatus)) throw new IllegalArgumentException("任务状态不正确");
        return repository.findMyTasks(requireExecutor(authorization), normalizedStatus, keyword, page, size);
    }

    public Map<String, Object> detail(String authorization, long taskId) {
        long userId = requireExecutor(authorization);
        Map<String, Object> task = repository.findMyTask(taskId, userId);
        if (task == null) throw new IllegalArgumentException("任务不存在或未分配给当前人员");
        return task;
    }

    @Transactional
    public Map<String, Object> start(String authorization, long taskId) {
        long userId = requireExecutor(authorization);
        Map<String, Object> task = repository.findMyTask(taskId, userId);
        if (task == null) throw new IllegalArgumentException("任务不存在或未分配给当前人员");
        String rawStatus = String.valueOf(task.get("rawStatus"));
        if ("IN_PROGRESS".equals(rawStatus)) return task;
        if (!"PENDING".equals(rawStatus)) throw new IllegalArgumentException("只有待执行任务可以开始");
        if (repository.startTask(taskId, userId) != 1) {
            throw new IllegalStateException("任务状态已变化，请刷新后重试");
        }
        notificationService.publishAll("任务更新", "应急任务已开始执行",
                String.valueOf(task.get("taskNo")), "/dispatch/progress");
        return repository.findMyTask(taskId, userId);
    }

    @Transactional
    public Map<String, Object> complete(String authorization, long taskId, String feedbackText,
                                         List<MultipartFile> images) {
        long userId = requireExecutor(authorization);
        Map<String, Object> task = repository.findMyTask(taskId, userId);
        if (task == null) throw new IllegalArgumentException("任务不存在或未分配给当前人员");
        if (!"IN_PROGRESS".equals(String.valueOf(task.get("rawStatus")))) {
            throw new IllegalArgumentException("请先开始执行任务，再提交完成反馈");
        }
        String text = feedbackText == null ? "" : feedbackText.trim();
        if (text.isBlank() || text.length() > 2000) {
            throw new IllegalArgumentException("完成说明不能为空且不能超过2000个字符");
        }
        String imageUrls = imageStorageService.saveImages(images);
        if (repository.completeTask(taskId, userId) != 1) {
            throw new IllegalStateException("任务状态已变化，请刷新后重试");
        }
        if (repository.insertFeedback(taskId, text, imageUrls, userId) != 1) {
            throw new IllegalStateException("现场反馈保存失败");
        }
        notificationService.publishAll("任务更新", "应急任务已完成并反馈",
                String.valueOf(task.get("taskNo")), "/dispatch/progress");
        return repository.findMyTask(taskId, userId);
    }

    private long requireExecutor(String authorization) {
        long userId = tokenService.requireIdentity(authorization).userId();
        String role = repository.findRole(userId);
        if (!Set.of("FRONT", "SECURITY").contains(role)) {
            throw new IllegalArgumentException("仅一线执行或后勤安保人员可以操作本人任务");
        }
        return userId;
    }

    private void validatePage(int page, int size) {
        if (page < 1 || size < 1 || size > 100) throw new IllegalArgumentException("分页参数不正确");
    }
}
