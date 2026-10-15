package com.metro.emergency.dto;

/** 调度人员向事件所属车站下发正式处置指令。 */
public record DispatchCommandRequest(String finalLevel, String content) {
}
