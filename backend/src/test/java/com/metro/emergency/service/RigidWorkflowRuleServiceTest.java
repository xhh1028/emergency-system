package com.metro.emergency.service;

import com.metro.emergency.dto.DispatchCloseRequest;
import com.metro.emergency.dto.DispatchCommandRequest;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class RigidWorkflowRuleServiceTest {

    private final RigidWorkflowRuleService rules = new RigidWorkflowRuleService();

    @Test
    void seriousStationDecisionAlwaysReportsToDispatch() {
        var decision = rules.validateStationDecision(
                Map.of("status", "PENDING"), "SERIOUS", "TASK_ASSIGN");
        assertEquals("SERIOUS", decision.level());
        assertEquals("TASK_ASSIGN", decision.route());
        org.junit.jupiter.api.Assertions.assertTrue(decision.reportToDispatch());
    }

    @Test
    void stationDecisionRejectsAlreadyDispatchedEvent() {
        assertThrows(IllegalStateException.class, () -> rules.validateStationDecision(
                Map.of("status", "REPORTED_TO_DISPATCH"), "GENERAL", "TASK_ASSIGN"));
    }

    @Test
    void commandRequiresDispatchConfirmationAndLegalLevel() {
        Map<String, Object> event = new HashMap<>();
        event.put("status", "REPORTED_TO_DISPATCH");
        event.put("dispatchConfirmed", true);
        var command = rules.validateCommand(event,
                new DispatchCommandRequest("II_SERIOUS", "立即组织现场处置"));
        assertEquals("II_SERIOUS", command.finalLevel());
        assertThrows(IllegalArgumentException.class, () -> rules.validateCommand(event,
                new DispatchCommandRequest("INVALID", "立即组织现场处置")));
    }

    @Test
    void closeRequiresEveryTaskCompleted() {
        Map<String, Object> event = new HashMap<>();
        event.put("status", "REPORTED_TO_DISPATCH");
        event.put("taskCount", 2);
        event.put("completedCount", 1);
        assertThrows(IllegalArgumentException.class,
                () -> rules.validateClose(event, new DispatchCloseRequest("II_SERIOUS")));
    }

    @Test
    void closeAcceptsCompletedTasksAndDefaultsLegalLevel() {
        Map<String, Object> event = new HashMap<>();
        event.put("status", "REPORTED_TO_DISPATCH");
        event.put("taskCount", 1);
        event.put("completedCount", 1);
        event.put("missingFeedbackCount", 0);
        event.put("finalLevel", null);
        var close = rules.validateClose(event, new DispatchCloseRequest(null));
        assertEquals("IV_GENERAL", close.finalLevel());
    }

    @Test
    void closeRejectsCompletedTaskWithoutFeedback() {
        Map<String, Object> event = new HashMap<>();
        event.put("status", "REPORTED_TO_DISPATCH");
        event.put("taskCount", 1);
        event.put("completedCount", 1);
        event.put("missingFeedbackCount", 1);
        assertThrows(IllegalArgumentException.class,
                () -> rules.validateClose(event, new DispatchCloseRequest("II_SERIOUS")));
    }
}
