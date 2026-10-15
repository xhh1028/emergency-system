package com.metro.emergency.dto;

import java.util.List;

/** 一个事件批量创建多条子任务；调度指令来源需同时提供已签收的 commandId。 */
public record TaskBatchRequest(String source, Long commandId, List<TaskDraft> tasks) {
}
