package com.metro.emergency.dto;

/** 险情上报成功响应。 */
public record EventReportResponse(long id, String eventNo, String status) {
}
