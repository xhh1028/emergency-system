package com.metro.emergency.service;

import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.dto.PersonnelSaveRequest;
import com.metro.emergency.dto.ResetPasswordRequest;
import com.metro.emergency.dto.StationDecisionResponse;
import com.metro.emergency.dto.StationEventDecisionRequest;
import com.metro.emergency.dto.TaskBatchRequest;
import com.metro.emergency.dto.TaskBatchResponse;
import com.metro.emergency.dto.TaskDraft;
import com.metro.emergency.repository.StationWorkflowRepository;
import com.metro.emergency.security.TokenService;
import com.metro.emergency.security.PasswordHasher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Set;

/** 车站管理员事件复核与站内任务分派业务。 */
@Service
public class StationWorkflowService {

    private static final Set<String> LEVELS = Set.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS");
    private static final Set<String> ROUTES = Set.of("TASK_ASSIGN", "DISPATCH");
    private final StationWorkflowRepository repository;
    private final TokenService tokenService;
    private final PasswordHasher passwordHasher;
    private final RealtimeNotificationService notificationService;

    public StationWorkflowService(StationWorkflowRepository repository, TokenService tokenService,
                                  PasswordHasher passwordHasher,
                                  RealtimeNotificationService notificationService) {
        this.repository = repository;
        this.tokenService = tokenService;
        this.passwordHasher = passwordHasher;
        this.notificationService = notificationService;
    }

    public PageResponse<Map<String, Object>> events(String authorization, String status,
                                                    String keyword, int page, int size) {
        if (page < 1 || size < 1 || size > 100) {
            throw new IllegalArgumentException("分页参数不正确");
        }
        long stationId = requireStationManager(authorization);
        return repository.findStationEvents(stationId, status, keyword, page, size);
    }

    public Map<String, Object> eventDetail(String authorization, long eventId) {
        long stationId = requireStationManager(authorization);
        Map<String, Object> event = repository.findStationEvent(eventId, stationId);
        if (event == null) throw new IllegalArgumentException("事件不存在或不属于当前车站");
        return event;
    }

    @Transactional
    public StationDecisionResponse decide(String authorization, long eventId,
                                           StationEventDecisionRequest request) {
        long stationId = requireStationManager(authorization);
        long operatorId = tokenService.requireIdentity(authorization).userId();
        if (request == null || !LEVELS.contains(request.level())) {
            throw new IllegalArgumentException("复核等级不正确");
        }
        if (!ROUTES.contains(request.route())) {
            throw new IllegalArgumentException("后续处置路径不正确");
        }
        Map<String, Object> event = repository.findStationEvent(eventId, stationId);
        if (event == null) {
            throw new IllegalArgumentException("事件不存在或不属于当前车站");
        }
        // 已驳回的事件必须先由一线补全重新提交，不能直接定级
        String currentStatus = String.valueOf(event.get("status"));
        if (!Set.of("PENDING", "CONFIRMED").contains(currentStatus)) {
            throw new IllegalStateException("当前事件状态不允许定级操作");
        }
        boolean emergency = Boolean.TRUE.equals(event.get("isEmergency"));
        String level = request.level();
        // 定级结果为较重/严重（SERIOUS/EXTREMELY_SERIOUS）时，无论是否紧急都必须上报调度指挥中心确认
        boolean mustReport = "SERIOUS".equals(level) || "EXTREMELY_SERIOUS".equals(level);
        boolean upReport = mustReport || "DISPATCH".equals(request.route());
        String status = upReport ? "REPORTED_TO_DISPATCH" : "STATION_HANDLE";
        if (repository.decide(eventId, stationId, level, status, upReport) != 1) {
            throw new IllegalStateException("事件复核失败");
        }
        // 流转日志：紧急场景跳过驳回记录、AI 研判结果、人工最终等级、上报调度
        String aiLevel = event.get("aiLevel") == null ? "" : String.valueOf(event.get("aiLevel"));
        if (emergency) {
            repository.insertEventLog(eventId, "SKIP_REJECT", null, null,
                    "紧急险情跳过驳回流程，直接进入定级与任务分派", operatorId);
        }
        repository.insertEventLog(eventId, "AI_ASSESS", aiLevel, null, "AI 研判", operatorId);
        repository.insertEventLog(eventId, "MANUAL_LEVEL", aiLevel, level, "人工最终等级：" + level, operatorId);
        if (upReport) {
            repository.insertEventLog(eventId, "REPORT_DISPATCH", null, level,
                    "定级较重/严重，已上报调度指挥中心确认", operatorId);
            notificationService.publishToRole("DISPATCH", "事件上报", "车站上报调度事件",
                    "事件编号：" + eventId, "/dispatch/events");
        } else {
            notificationService.publishToStation(stationId, "事件复核", "事件已进入站内处置",
                    "事件编号：" + eventId, "/station/assign?eventId=" + eventId);
        }
        String nextPath = upReport ? "/station/report?eventId=" + eventId : "/station/assign?eventId=" + eventId;
        return new StationDecisionResponse(status, nextPath);
    }

    /** 普通险情驳回：写明理由退回一线补全信息。紧急险情禁止驳回，避免延误应急处置。 */
    @Transactional
    public void reject(String authorization, long eventId, String reason) {
        long stationId = requireStationManager(authorization);
        long operatorId = tokenService.requireIdentity(authorization).userId();
        if (repository.findStationEvent(eventId, stationId) == null) {
            throw new IllegalArgumentException("事件不存在或不属于当前车站");
        }
        String text = reason == null ? "" : reason.trim();
        if (text.isBlank() || text.length() > 500) {
            throw new IllegalArgumentException("请填写驳回理由（500字以内）");
        }
        if (repository.rejectEvent(eventId, stationId, text) != 1) {
            throw new IllegalStateException("仅普通险情且处于待处理状态的事件可以驳回，紧急险情禁止驳回");
        }
        repository.insertEventLog(eventId, "REJECT", null, null, "车站管理员驳回：" + text, operatorId);
    }

    public List<Map<String, Object>> personnel(String authorization) {
        return repository.findPersonnel(requireStationManager(authorization));
    }

    public List<Map<String, Object>> personnelPosts(String authorization) {
        requireStationManager(authorization);
        return repository.findPersonnelPosts();
    }

    @Transactional
    public Map<String, Object> createPersonnel(String authorization, PersonnelSaveRequest request) {
        long stationId = requireStationManager(authorization);
        PersonnelValues values = validatePersonnel(request, null, true);
        long id = repository.insertPersonnel(stationId, values.realName(), values.phone(),
                passwordHasher.hash(request.initialPassword()), values.roleId(), values.postId(), values.status());
        return repository.findPersonnelById(id, stationId);
    }

    @Transactional
    public Map<String, Object> updatePersonnel(String authorization, long id, PersonnelSaveRequest request) {
        long stationId = requireStationManager(authorization);
        if (repository.findPersonnelById(id, stationId) == null) {
            throw new IllegalArgumentException("人员不存在或不属于当前车站");
        }
        PersonnelValues values = validatePersonnel(request, id, false);
        if (repository.updatePersonnel(id, stationId, values.realName(), values.phone(),
                values.roleId(), values.postId(), values.status()) != 1) {
            throw new IllegalStateException("人员信息更新失败");
        }
        return repository.findPersonnelById(id, stationId);
    }

    @Transactional
    public void resetPersonnelPassword(String authorization, long id, ResetPasswordRequest request) {
        long stationId = requireStationManager(authorization);
        String password = request == null ? null : request.newPassword();
        validatePassword(password, "新密码");
        if (repository.resetPersonnelPassword(id, stationId, passwordHasher.hash(password)) != 1) {
            throw new IllegalArgumentException("人员不存在或不属于当前车站");
        }
    }

    public PageResponse<Map<String, Object>> commands(String authorization, String status,
                                                      String keyword, int page, int size) {
        validatePage(page, size);
        return repository.findCommands(requireStationManager(authorization), status, keyword, page, size);
    }

    public Map<String, Object> commandDetail(String authorization, long commandId) {
        Map<String, Object> command = repository.findCommand(commandId, requireStationManager(authorization));
        if (command == null) throw new IllegalArgumentException("指令不存在或不属于当前车站");
        return command;
    }

    @Transactional
    public Map<String, Object> signCommand(String authorization, long commandId) {
        var identity = tokenService.requireIdentity(authorization);
        long stationId = requireStationManager(authorization);
        Map<String, Object> command = repository.findCommand(commandId, stationId);
        if (command == null) throw new IllegalArgumentException("指令不存在或不属于当前车站");
        if (Boolean.TRUE.equals(command.get("read"))) return command;
        if (repository.signCommand(commandId, stationId, identity.userId()) != 1) {
            throw new IllegalStateException("指令签收失败，请刷新后重试");
        }
        command.put("read", true);
        command.put("receiveUserId", identity.userId());
        notificationService.publishToRole("DISPATCH", "指令签收", "车站已签收调度指令",
                String.valueOf(command.get("content")), "/dispatch/progress");
        return command;
    }

    public PageResponse<Map<String, Object>> taskProgress(String authorization, Long eventId, String status,
                                                          String keyword, int page, int size) {
        validatePage(page, size);
        return repository.findTaskProgress(requireStationManager(authorization), eventId, status, keyword, page, size);
    }

    /** 查询本站各事件的子任务总进度，供进度监控页顶部展示事件级进度条。 */
    public List<Map<String, Object>> eventTaskProgress(String authorization) {
        return repository.findEventProgress(requireStationManager(authorization));
    }

    public Map<String, Object> taskDetail(String authorization, long taskId) {
        Map<String, Object> task = repository.findTaskDetail(taskId, requireStationManager(authorization));
        if (task == null) throw new IllegalArgumentException("任务不存在或不属于当前车站");
        return task;
    }

    @Transactional
    public TaskBatchResponse createTasks(String authorization, long eventId, TaskBatchRequest request) {
        long stationId = requireStationManager(authorization);
        Map<String, Object> event = repository.findStationEvent(eventId, stationId);
        if (event == null) throw new IllegalArgumentException("事件不存在或不属于当前车站");
        if (request == null || request.tasks() == null || request.tasks().isEmpty()) {
            throw new IllegalArgumentException("至少需要创建一条处置任务");
        }
        if (request.tasks().size() > 20) {
            throw new IllegalArgumentException("单次最多创建20条处置任务");
        }
        // 子任务由车站拆分派发，来源固定为 STATION（车站指派）。
        // 依据业务规范：顶层事件来源才是调度指令，车站拆分的子任务禁止标记为调度指令。
        String source = "STATION";
        if (request.tasks().size() > 20) {
            throw new IllegalArgumentException("单次最多创建20条处置任务");
        }
        for (TaskDraft task : request.tasks()) {
            if (task == null || task.content() == null || task.content().isBlank()) {
                throw new IllegalArgumentException("任务内容不能为空");
            }
            if (task.executorId() == null
                    || !repository.executorBelongsToStation(task.executorId(), stationId)) {
                throw new IllegalArgumentException("执行人员必须是本站在岗的一线或后勤人员");
            }
        }
        int created = 0;
        for (TaskDraft task : request.tasks()) {
            created += repository.insertTask(eventId, stationId, source, task);
            notificationService.publishToUser(task.executorId(), "任务分配", "收到新的应急任务",
                    task.content().trim(), "/field/tasks");
        }
        repository.markHandling(eventId, stationId, source);
        notificationService.publishToRole("DISPATCH", "任务更新", "车站已完成任务分派",
                "事件编号：" + eventId, "/dispatch/progress");
        return new TaskBatchResponse(created);
    }

    private long requireStationManager(String authorization) {
        long userId = tokenService.requireIdentity(authorization).userId();
        StationWorkflowRepository.UserScope scope = repository.findUserScope(userId);
        if (scope == null || !"STATION".equalsIgnoreCase(scope.role())) {
            throw new IllegalArgumentException("仅车站管理员可以执行此操作");
        }
        if (scope.stationId() == null) {
            throw new IllegalArgumentException("当前管理员未绑定所属车站");
        }
        return scope.stationId();
    }

    private void validatePage(int page, int size) {
        if (page < 1 || size < 1 || size > 100) {
            throw new IllegalArgumentException("分页参数不正确");
        }
    }

    private PersonnelValues validatePersonnel(PersonnelSaveRequest request, Long excludedId,
                                               boolean creating) {
        if (request == null) throw new IllegalArgumentException("人员信息不能为空");
        String name = request.realName() == null ? "" : request.realName().trim();
        String phone = request.phone() == null ? "" : request.phone().trim();
        String role = request.role() == null ? "" : request.role().toUpperCase();
        String status = request.status() == null ? "" : request.status().toUpperCase();
        if (name.isBlank() || name.length() > 40) {
            throw new IllegalArgumentException("姓名不能为空且不能超过40个字符");
        }
        if (!phone.matches("1\\d{10}")) {
            throw new IllegalArgumentException("请输入正确的11位手机号码");
        }
        if (!Set.of("FRONT", "SECURITY").contains(role)) {
            throw new IllegalArgumentException("人员类别只能是一线执行或后勤安保");
        }
        if (!Set.of("ON_DUTY", "REST", "LEAVE", "OUT").contains(status)) {
            throw new IllegalArgumentException("人员在岗状态不正确");
        }
        if (request.postId() == null) throw new IllegalArgumentException("请选择具体岗位");
        Integer roleId = repository.findRoleId(role);
        if (roleId == null || !repository.postMatchesRole(request.postId(), roleId)) {
            throw new IllegalArgumentException("岗位与人员类别不匹配");
        }
        if (repository.phoneExists(phone, excludedId)) {
            throw new IllegalArgumentException("该手机号码已被其他账号使用");
        }
        if (creating) validatePassword(request.initialPassword(), "初始密码");
        return new PersonnelValues(name, phone, roleId, request.postId(), status);
    }

    private void validatePassword(String password, String label) {
        if (password == null || password.length() < 6 || password.length() > 32) {
            throw new IllegalArgumentException(label + "长度必须为6至32位");
        }
    }

    private record PersonnelValues(String realName, String phone, int roleId, int postId, String status) {
    }
}
