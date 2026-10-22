package com.metro.emergency.service;

import com.metro.emergency.dto.StationEventDecisionRequest;
import com.metro.emergency.repository.StationWorkflowRepository;
import com.metro.emergency.security.PasswordHasher;
import com.metro.emergency.security.TokenService;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class StationEmergencyWorkflowTest {
    private final StationWorkflowRepository repository = mock(StationWorkflowRepository.class);
    private final TokenService tokens = new TokenService();
    private final RealtimeNotificationService notifications = mock(RealtimeNotificationService.class);
    private final StationWorkflowService service = new StationWorkflowService(repository, tokens,
            new PasswordHasher(), notifications, new RigidWorkflowRuleService());
    private final String auth = "Bearer " + tokens.issue(7L, "station-manager");

    @Test
    void emergencyDecisionSkipsRejectionAndRecordsThatTransition() {
        when(repository.findUserScope(7L)).thenReturn(new StationWorkflowRepository.UserScope(3L, "STATION"));
        when(repository.findStationEvent(12L, 3L)).thenReturn(Map.of(
                "status", "PENDING", "isEmergency", true, "aiLevel", "SERIOUS"));
        when(repository.decide(12L, 3L, "GENERAL", "STATION_HANDLE", false)).thenReturn(1);

        service.decide(auth, 12L, new StationEventDecisionRequest("GENERAL", "TASK_ASSIGN"));

        verify(repository).insertEventLog(12L, "SKIP_REJECT", null, null,
                "紧急险情跳过驳回流程，直接进入定级与任务分派", 7L);
        verify(repository, never()).rejectEvent(anyLong(), anyLong(), anyString());
    }

    @Test
    void emergencyEventCannotUseOrdinaryRejectEndpoint() {
        when(repository.findUserScope(7L)).thenReturn(new StationWorkflowRepository.UserScope(3L, "STATION"));
        when(repository.findStationEvent(12L, 3L)).thenReturn(Map.of("status", "PENDING", "isEmergency", true));
        when(repository.rejectEvent(12L, 3L, "退回补充信息")).thenReturn(0);

        assertThrows(IllegalStateException.class,
                () -> service.reject(auth, 12L, "退回补充信息"));

        verify(repository, never()).insertEventLog(eq(12L), eq("REJECT"), any(), any(), anyString(), anyLong());
    }
}
