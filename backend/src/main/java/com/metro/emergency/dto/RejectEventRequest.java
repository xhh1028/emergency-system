package com.metro.emergency.dto;

/** 车站管理员驳回普通险情事件的请求体。 */
public record RejectEventRequest(String reason) {
}