package com.metro.emergency.dto;

/** 调度关闭事件时可补充法定等级。 */
public record DispatchCloseRequest(String finalLevel) {
}
