package com.metro.emergency.dto;

/** 复核完成后返回事件状态和前端下一步页面。 */
public record StationDecisionResponse(String status, String nextPath) {
}
