package com.metro.emergency.service;

import com.metro.emergency.dto.EventReportResponse;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.repository.EventRepository;
import com.metro.emergency.security.TokenService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** 险情上报与个人历史记录业务服务。 */
@Service
public class EventService {

    private static final Set<String> EVENT_TYPES = Set.of(
            "DEVICE_FAILURE", "FIRE", "PASSENGER", "TRACK_OPERATION",
            "CROWD_SECURITY", "DISASTER_ENVIRONMENT", "OTHER");
    private static final Set<String> LEVELS = Set.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS");
    private final EventRepository repository;
    private final TokenService tokenService;
    private final AiAssessmentService aiAssessmentService;
    private final ImageStorageService imageStorageService;
    private final RealtimeNotificationService notificationService;

    public EventService(EventRepository repository, TokenService tokenService,
                        AiAssessmentService aiAssessmentService,
                        ImageStorageService imageStorageService,
                        RealtimeNotificationService notificationService) {
        this.repository = repository;
        this.tokenService = tokenService;
        this.aiAssessmentService = aiAssessmentService;
        this.imageStorageService = imageStorageService;
        this.notificationService = notificationService;
    }

    @Transactional
    public EventReportResponse report(String authorization, String eventType, String preLevel,
                                      String eventTitle, String faultyDevice, String description,
                                      boolean isEmergency, List<MultipartFile> images) {
        var identity = tokenService.requireIdentity(authorization);
        if (!EVENT_TYPES.contains(eventType)) {
            throw new IllegalArgumentException("突发状况类型不正确");
        }
        // 定级权限仅调度指挥中心：一线险情上报不填写等级。
        // 未传等级时统一记为 UNCONFIRMED（待确认），最终法定等级由调度确认/AI 研判确定。
        String reportedLevel = preLevel == null || preLevel.isBlank() ? "UNCONFIRMED" : preLevel.toUpperCase();
        if (!"UNCONFIRMED".equals(reportedLevel) && !LEVELS.contains(reportedLevel)) {
            throw new IllegalArgumentException("预判等级不正确");
        }
        if (description == null || description.isBlank()) {
            throw new IllegalArgumentException("事件描述不能为空");
        }
        String title = eventTitle == null ? "" : eventTitle.trim();
        if (title.isBlank() || title.length() > 200) {
            throw new IllegalArgumentException("事件标题不能为空且不能超过200个字符");
        }
        String device = faultyDevice == null ? "" : faultyDevice.trim();
        if (device.length() > 200) {
            throw new IllegalArgumentException("故障设备不能超过200个字符");
        }
        if ("DEVICE_FAILURE".equals(eventType) && device.isBlank()) {
            throw new IllegalArgumentException("设备故障事件必须填写故障设备");
        }
        Long stationId = repository.findStationId(identity.userId());
        if (stationId == null) {
            throw new IllegalArgumentException("当前人员未绑定所属车站，无法上报");
        }

        String imageUrls = imageStorageService.saveImages(images);
        String eventNo = "EV-" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"))
                + "-" + UUID.randomUUID().toString().substring(0, 4).toUpperCase();
        EventReportResponse response = repository.insertEvent(
                eventNo, eventType, reportedLevel, stationId, title, device,
                description.trim(), imageUrls, identity.userId(), isEmergency);
        AiAssessmentService.Assessment assessment =
                aiAssessmentService.assess(eventType, description, reportedLevel);
        if (repository.updateAiAssessment(response.id(), assessment) != 1) {
            throw new IllegalStateException("事件已保存，但 AI 研判结果写入失败");
        }
        // 流转日志：紧急标记 + AI 研判结果
        repository.insertEventLog(response.id(), "REPORT", assessment.level(), null,
                (isEmergency ? "紧急险情" : "普通险情") + "上报", identity.userId());
        notificationService.publishToStation(stationId, "事件上报", "收到新的险情上报",
                title + "（" + eventNo + "）", "/station/events");
        notificationService.publishToRole("DISPATCH", "事件更新", "险情数据已更新",
                title + "（" + eventNo + "）", "/dispatch/overview");
        return response;
    }

    /** 一线补全信息后重新提交被驳回的普通险情事件。 */
    @Transactional
    public Map<String, Object> resubmit(String authorization, long eventId, String eventTitle,
                                        String faultyDevice, String description, List<MultipartFile> images) {
        var identity = tokenService.requireIdentity(authorization);
        if (description == null || description.isBlank()) {
            throw new IllegalArgumentException("事件描述不能为空");
        }
        String title = eventTitle == null ? "" : eventTitle.trim();
        if (title.isBlank() || title.length() > 200) {
            throw new IllegalArgumentException("事件标题不能为空且不能超过200个字符");
        }
        String device = faultyDevice == null ? "" : faultyDevice.trim();
        if (device.length() > 200) {
            throw new IllegalArgumentException("故障设备不能超过200个字符");
        }
        String imageUrls = imageStorageService.saveImages(images);
        if (repository.resubmitEvent(eventId, identity.userId(), title, device,
                description.trim(), imageUrls) != 1) {
            throw new IllegalArgumentException("只有本人被驳回的事件可以补充重新提交");
        }
        repository.insertEventLog(eventId, "RESUBMIT", null, null,
                "一线补全信息后重新提交，状态改为已确认", identity.userId());
        return Map.of("eventId", eventId);
    }

    /** 撤回自己发起、且仍处于待处理状态的险情事件。
     *  撤回为逻辑删除：仅将 is_withdraw 置 1，禁止物理删除，操作写入 event_log 留痕。 */
    @Transactional
    public Map<String, Object> withdraw(String authorization, long eventId) {
        var identity = tokenService.requireIdentity(authorization);
        Map<String, Object> event = repository.findMyEvent(eventId, identity.userId());
        if (event == null) {
            throw new IllegalArgumentException("事件不存在或无权撤回");
        }
        // 前置条件：仅 PENDING 待处理且未撤回的事件允许撤回；
        // 一旦做过定级、驳回、分派等处理，状态变更后一律禁止撤回
        if (!"PENDING".equals(String.valueOf(event.get("status")))) {
            throw new IllegalStateException("事件已经被处理，不允许撤回");
        }
        if (Boolean.TRUE.equals(event.get("isWithdraw"))) {
            throw new IllegalStateException("事件已撤回，请勿重复操作");
        }
        if (repository.withdrawEvent(eventId, identity.userId()) != 1) {
            throw new IllegalStateException("事件撤回失败，请刷新后重试");
        }
        // 业务留痕：operate_type=WITHDRAW，记录操作人ID、事件ID、操作时间、操作描述
        repository.insertEventLog(eventId, "WITHDRAW", null, null,
                "事件被发起人撤回（逻辑删除）", identity.userId());
        return Map.of("eventId", eventId);
    }

    public PageResponse<Map<String, Object>> myEvents(String authorization, String keyword,
                                                       LocalDateTime start, LocalDateTime end,
                                                       int page, int size) {
        validatePage(page, size);
        long userId = tokenService.requireIdentity(authorization).userId();
        return repository.findMyEvents(userId, keyword, start, end, page, size);
    }

    public PageResponse<Map<String, Object>> completedTasks(String authorization, String keyword,
                                                             LocalDateTime start, LocalDateTime end,
                                                             int page, int size) {
        validatePage(page, size);
        long userId = tokenService.requireIdentity(authorization).userId();
        return repository.findCompletedTasks(userId, keyword, start, end, page, size);
    }

    private void validatePage(int page, int size) {
        if (page < 1 || size < 1 || size > 100) {
            throw new IllegalArgumentException("分页参数不正确");
        }
    }
}
