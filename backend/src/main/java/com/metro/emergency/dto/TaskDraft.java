package com.metro.emergency.dto;

import java.time.LocalDateTime;

/** 站内拆分的一条子任务。 */
public record TaskDraft(String content, Long executorId, LocalDateTime deadline) {
}
