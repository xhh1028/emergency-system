package com.metro.emergency.dto;

/**
 * 登录页可选身份。
 */
public record RoleInfo(long id, String roleKey, String roleName, String defaultPath) {
}
