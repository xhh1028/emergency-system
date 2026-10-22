package com.metro.emergency.controller;

import com.metro.emergency.dto.EventReportResponse;
import com.metro.emergency.repository.EventRepository;
import com.metro.emergency.repository.DispatchWorkflowRepository;
import com.metro.emergency.repository.PlanRepository;
import com.metro.emergency.repository.StationWorkflowRepository;
import com.metro.emergency.repository.TaskExecutionRepository;
import com.metro.emergency.repository.UserAccount;
import com.metro.emergency.repository.UserRepository;
import com.metro.emergency.repository.WorkflowArtifactRepository;
import com.metro.emergency.security.PasswordHasher;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.SimpleTransactionStatus;

import javax.sql.DataSource;
import java.util.Optional;
import java.util.Map;
import java.util.List;
import java.util.LinkedHashMap;

import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 登录接口集成测试。
 */
@SpringBootTest
@AutoConfigureMockMvc
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private PasswordHasher passwordHasher;

    @Autowired
    private com.metro.emergency.service.AiAssessmentService aiAssessmentService;

    @MockBean
    private UserRepository userRepository;

    @MockBean
    private EventRepository eventRepository;

    @MockBean
    private PlanRepository planRepository;

    @MockBean
    private WorkflowArtifactRepository workflowArtifactRepository;

    @MockBean
    private StationWorkflowRepository stationWorkflowRepository;

    @MockBean
    private DispatchWorkflowRepository dispatchWorkflowRepository;

    @MockBean
    private TaskExecutionRepository taskExecutionRepository;

    // 测试环境不连接真实 RDS，避免自动配置尝试创建数据源。
    @MockBean
    private DataSource dataSource;

    @MockBean
    private PlatformTransactionManager transactionManager;

    @BeforeEach
    void prepareUser() {
        UserAccount admin = new UserAccount(
                1, "admin", passwordHasher.hash("123456"), "张调度",
                "dispatch_center", "调度指挥", "", "", "", true, 1L, "西直门站");
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(admin));
        UserAccount stationManager = new UserAccount(
                2, "station", passwordHasher.hash("123456"), "李站长",
                "station", "车站管理", "", "", "", true, 1L, "测试站");
        when(userRepository.findByUsername("station")).thenReturn(Optional.of(stationManager));
        UserAccount field = new UserAccount(
                3, "field", passwordHasher.hash("123456"), "王执行",
                "field", "一线执行", "", "", "", true, 1L, "测试站");
        when(userRepository.findByUsername("field")).thenReturn(Optional.of(field));
        when(transactionManager.getTransaction(any())).thenReturn(new SimpleTransactionStatus());
    }

    @Test
    void shouldReturnRoleList() throws Exception {
        mockMvc.perform(get("/api/auth/roles"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data[0].roleKey").value("dispatch_center"));
    }

    @Test
    void shouldLoginSuccessfully() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"admin","password":"123456"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.token").isNotEmpty())
                .andExpect(jsonPath("$.data.userInfo.role").value("dispatch_center"));
    }

    @Test
    void shouldRejectWrongPassword() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"admin","password":"wrong"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401))
                .andExpect(jsonPath("$.message").value("用户名或密码错误"));
    }

    @Test
    void shouldValidateBlankUsername() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"","password":"123456"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.message").value("用户名不能为空"));
    }

    @Test
    void shouldChangePasswordWithLoginToken() throws Exception {
        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"admin","password":"123456"}
                                """))
                .andReturn().getResponse().getContentAsString();
        String token = new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(loginResponse).path("data").path("token").asText();
        when(userRepository.updatePasswordHash(anyString(), anyString())).thenReturn(1);

        mockMvc.perform(post("/api/auth/change-password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"oldPassword":"123456","newPassword":"654321"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    void shouldReturnCurrentUsersDatabaseProfile() throws Exception {
        String token = fieldToken();
        when(userRepository.findProfile(3L)).thenReturn(Map.of(
                "id", 3L, "phone", "field", "realName", "王执行",
                "role", "field", "roleName", "一线执行", "postName", "站台岗",
                "status", "ON_DUTY", "stationName", "测试站", "lineName", 1));

        mockMvc.perform(get("/api/auth/profile").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.realName").value("王执行"))
                .andExpect(jsonPath("$.data.postName").value("站台岗"))
                .andExpect(jsonPath("$.data.status").value("ON_DUTY"));
    }

    @Test
    void shouldReportEventWithLoginToken() throws Exception {
        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"admin","password":"123456"}
                                """))
                .andReturn().getResponse().getContentAsString();
        String token = new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(loginResponse).path("data").path("token").asText();
        when(eventRepository.findStationId(1L)).thenReturn(1L);
        when(eventRepository.insertEvent(
                anyString(), anyString(), anyString(), anyLong(), anyString(), anyString(),
                anyString(), anyString(), anyLong(), anyBoolean()))
                .thenReturn(new EventReportResponse(8L, "EV-TEST-0001", "PENDING_ASSIGN"));
        when(eventRepository.updateAiAssessment(eq(8L), any())).thenReturn(1);

        mockMvc.perform(multipart("/api/events/report")
                        .header("Authorization", "Bearer " + token)
                        .param("eventType", "FIRE")
                        .param("preLevel", "SERIOUS")
                        .param("eventTitle", "站台烟雾险情")
                        .param("description", "站台发现少量烟雾，已进行现场警戒"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.eventNo").value("EV-TEST-0001"))
                .andExpect(jsonPath("$.data.status").value("PENDING_ASSIGN"));
    }

    @Test
    void shouldListStationEventsForStationManager() throws Exception {
        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"station","password":"123456"}
                                """))
                .andReturn().getResponse().getContentAsString();
        String token = new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(loginResponse).path("data").path("token").asText();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stationWorkflowRepository.findStationEvents(1L, "ALL", null, 1, 10))
                .thenReturn(new com.metro.emergency.dto.PageResponse<>(List.of(), 0, 1, 10));

        mockMvc.perform(get("/api/station/events")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    void shouldListDispatchCommandsForStationManager() throws Exception {
        String token = stationToken();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stationWorkflowRepository.findCommands(1L, "UNREAD", null, 1, 10))
                .thenReturn(new com.metro.emergency.dto.PageResponse<>(List.of(), 0, 1, 10));

        mockMvc.perform(get("/api/station/commands")
                        .header("Authorization", "Bearer " + token)
                        .param("status", "UNREAD"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    void shouldSignDispatchCommandForStationManager() throws Exception {
        String token = stationToken();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        Map<String, Object> command = new LinkedHashMap<>();
        command.put("id", 9L);
        command.put("read", false);
        when(stationWorkflowRepository.findCommand(9L, 1L)).thenReturn(command);
        when(stationWorkflowRepository.signCommand(9L, 1L, 2L)).thenReturn(1);

        mockMvc.perform(post("/api/station/commands/9/sign")
                        .header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.read").value(true))
                .andExpect(jsonPath("$.data.receiveUserId").value(2));
    }

    @Test
    void shouldListTaskProgressForStationManager() throws Exception {
        String token = stationToken();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stationWorkflowRepository.findTaskProgress(1L, null, "COMPLETED", null, 1, 10))
                .thenReturn(new com.metro.emergency.dto.PageResponse<>(List.of(), 0, 1, 10));

        mockMvc.perform(get("/api/station/tasks/progress")
                        .header("Authorization", "Bearer " + token)
                        .param("status", "COMPLETED"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    void shouldCreateStationPersonnel() throws Exception {
        String token = stationToken();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stationWorkflowRepository.findRoleId("FRONT")).thenReturn(1);
        when(stationWorkflowRepository.postMatchesRole(1, 1)).thenReturn(true);
        when(stationWorkflowRepository.phoneExists("13800009991", null)).thenReturn(false);
        when(stationWorkflowRepository.insertPersonnel(eq(1L), eq("测试人员"), eq("13800009991"),
                anyString(), eq(1), eq(1), eq("ON_DUTY"))).thenReturn(88L);
        when(stationWorkflowRepository.findPersonnelById(88L, 1L)).thenReturn(Map.of(
                "id", 88L, "name", "测试人员", "phone", "13800009991",
                "role", "FRONT", "postId", 1, "postName", "站台岗", "status", "ON_DUTY"));

        mockMvc.perform(post("/api/station/personnel")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"realName":"测试人员","phone":"13800009991","role":"FRONT",
                                 "postId":1,"status":"ON_DUTY","initialPassword":"123456"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.id").value(88))
                .andExpect(jsonPath("$.data.postName").value("站台岗"));
    }

    @Test
    void shouldResetStationPersonnelPassword() throws Exception {
        String token = stationToken();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stationWorkflowRepository.resetPersonnelPassword(eq(5L), eq(1L), anyString())).thenReturn(1);

        mockMvc.perform(post("/api/station/personnel/5/reset-password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"newPassword\":\"654321\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    void shouldRejectPersonnelFromAnotherStationWhenResettingPassword() throws Exception {
        String token = stationToken();
        when(stationWorkflowRepository.findUserScope(2L))
                .thenReturn(new StationWorkflowRepository.UserScope(1L, "STATION"));
        when(stationWorkflowRepository.resetPersonnelPassword(eq(99L), eq(1L), anyString())).thenReturn(0);

        mockMvc.perform(post("/api/station/personnel/99/reset-password")
                        .header("Authorization", "Bearer " + token)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"newPassword\":\"654321\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    void shouldListDispatchEvents() throws Exception {
        String token = adminToken();
        when(dispatchWorkflowRepository.findRole(1L)).thenReturn("DISPATCH");
        when(dispatchWorkflowRepository.findEvents("ALL", null, 1, 10))
                .thenReturn(new com.metro.emergency.dto.PageResponse<>(List.of(), 0, 1, 10));
        mockMvc.perform(get("/api/dispatch/events").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    void shouldLoadRealtimeDispatchOverview() throws Exception {
        String token = adminToken();
        when(dispatchWorkflowRepository.findRole(1L)).thenReturn("DISPATCH");
        when(dispatchWorkflowRepository.findOverview()).thenReturn(Map.of(
                "statistics", Map.of("totalEvents", 12, "activeEvents", 3,
                        "finishedEvents", 9, "alertStations", 2),
                "stations", List.of(), "latestEvents", List.of()));

        mockMvc.perform(get("/api/dispatch/overview").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.statistics.activeEvents").value(3))
                .andExpect(jsonPath("$.data.statistics.alertStations").value(2));
    }

    @Test
    void shouldListFinishedEventsFromRealArchive() throws Exception {
        String token = adminToken();
        when(dispatchWorkflowRepository.findRole(1L)).thenReturn("DISPATCH");
        when(dispatchWorkflowRepository.findArchive(null, "ALL", null, 1, 10))
                .thenReturn(new com.metro.emergency.dto.PageResponse<>(List.of(), 0, 1, 10));

        mockMvc.perform(get("/api/dispatch/archive").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    void shouldReturnAvailableArchiveYears() throws Exception {
        String token = adminToken();
        when(dispatchWorkflowRepository.findRole(1L)).thenReturn("DISPATCH");
        when(dispatchWorkflowRepository.findArchiveYears()).thenReturn(List.of(2026, 2025));

        mockMvc.perform(get("/api/dispatch/archive/years").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0]").value(2026));
    }

    @Test
    void shouldConfirmReportedDispatchEvent() throws Exception {
        String token = adminToken();
        when(dispatchWorkflowRepository.findRole(1L)).thenReturn("DISPATCH");
        Map<String, Object> pending = new LinkedHashMap<>();
        pending.put("id", 12L); pending.put("status", "REPORTED_TO_DISPATCH");
        pending.put("stationId", 1L); pending.put("eventNo", "EV-TEST-0012");
        pending.put("dispatchConfirmed", false);
        Map<String, Object> confirmed = new LinkedHashMap<>(pending); confirmed.put("dispatchConfirmed", true);
        when(dispatchWorkflowRepository.findEvent(12L)).thenReturn(pending, confirmed);
        when(dispatchWorkflowRepository.confirmEvent(12L)).thenReturn(1);
        mockMvc.perform(post("/api/dispatch/events/12/confirm").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.dispatchConfirmed").value(true));
    }

    @Test
    void shouldRejectCommandBeforeDispatchConfirmation() throws Exception {
        String token = adminToken();
        when(dispatchWorkflowRepository.findRole(1L)).thenReturn("DISPATCH");
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("status", "REPORTED_TO_DISPATCH"); event.put("dispatchConfirmed", false); event.put("stationId", 1L);
        when(dispatchWorkflowRepository.findEvent(12L)).thenReturn(event);
        mockMvc.perform(post("/api/dispatch/events/12/commands")
                        .header("Authorization", "Bearer " + token).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"finalLevel\":\"II_SERIOUS\",\"content\":\"立即组织现场处置\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.code").value(400));
    }

    @Test
    void shouldListOnlyCurrentExecutorsTasks() throws Exception {
        String token = fieldToken();
        when(taskExecutionRepository.findRole(3L)).thenReturn("FRONT");
        when(taskExecutionRepository.findMyTasks(3L, "ALL", null, 1, 10))
                .thenReturn(new com.metro.emergency.dto.PageResponse<>(List.of(), 0, 1, 10));

        mockMvc.perform(get("/api/tasks").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.total").value(0));
    }

    @Test
    void shouldStartAssignedTask() throws Exception {
        String token = fieldToken();
        when(taskExecutionRepository.findRole(3L)).thenReturn("FRONT");
        Map<String, Object> pending = new LinkedHashMap<>();
        pending.put("id", 21L);
        pending.put("eventId", 12L);
        pending.put("rawStatus", "PENDING");
        Map<String, Object> progressing = new LinkedHashMap<>(pending);
        progressing.put("rawStatus", "IN_PROGRESS");
        progressing.put("status", "IN_PROGRESS");
        when(taskExecutionRepository.findMyTask(21L, 3L)).thenReturn(pending, progressing);
        when(taskExecutionRepository.startTask(21L, 3L)).thenReturn(1);

        mockMvc.perform(post("/api/tasks/21/start").header("Authorization", "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.rawStatus").value("IN_PROGRESS"));
    }

    @Test
    void shouldCompleteTaskWithOnSiteFeedback() throws Exception {
        String token = fieldToken();
        when(taskExecutionRepository.findRole(3L)).thenReturn("FRONT");
        Map<String, Object> progressing = new LinkedHashMap<>();
        progressing.put("id", 21L);
        progressing.put("eventId", 12L);
        progressing.put("rawStatus", "IN_PROGRESS");
        Map<String, Object> completed = new LinkedHashMap<>(progressing);
        completed.put("rawStatus", "COMPLETED");
        completed.put("status", "COMPLETED");
        when(taskExecutionRepository.findMyTask(21L, 3L)).thenReturn(progressing, completed);
        when(taskExecutionRepository.completeTask(21L, 3L)).thenReturn(1);
        when(taskExecutionRepository.insertFeedback(21L, "现场处置完成，设备恢复正常", "", 3L)).thenReturn(1);

        mockMvc.perform(multipart("/api/tasks/21/complete")
                        .header("Authorization", "Bearer " + token)
                        .param("feedbackText", "现场处置完成，设备恢复正常"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.rawStatus").value("COMPLETED"));
    }

    @Test
    void aiAssessmentShouldEscalateFireWithSmoke() {
        var result = aiAssessmentService.assess("FIRE", "站台发生失火并伴有浓烟，多名乘客需要疏散", "SERIOUS");
        org.junit.jupiter.api.Assertions.assertEquals("EXTREMELY_SERIOUS", result.level());
        org.junit.jupiter.api.Assertions.assertEquals("RULE_FALLBACK", result.source());
    }

    private String stationToken() throws Exception {
        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"station","password":"123456"}
                                """))
                .andReturn().getResponse().getContentAsString();
        return new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(loginResponse).path("data").path("token").asText();
    }

    private String adminToken() throws Exception {
        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"admin\",\"password\":\"123456\"}"))
                .andReturn().getResponse().getContentAsString();
        return new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(loginResponse).path("data").path("token").asText();
    }

    private String fieldToken() throws Exception {
        String loginResponse = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"field\",\"password\":\"123456\"}"))
                .andReturn().getResponse().getContentAsString();
        return new com.fasterxml.jackson.databind.ObjectMapper()
                .readTree(loginResponse).path("data").path("token").asText();
    }
}
