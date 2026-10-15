package com.metro.emergency.dto;

/** 车站管理员复核事件等级和后续处置路径。 */
public record StationEventDecisionRequest(String level, String route) {
}
