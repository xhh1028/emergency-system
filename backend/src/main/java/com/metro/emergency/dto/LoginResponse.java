package com.metro.emergency.dto;

/**
 * 登录成功响应数据。
 */
public record LoginResponse(String token, UserInfo userInfo) {
}
