package com.metro.emergency.dto;

/**
 * 返回给前端的登录用户信息，不包含密码。
 */
public record UserInfo(
        long id,
        String username,
        String nickname,
        String role,
        String roleLabel,
        String subRole,
        String subRoleLabel,
        String avatar
) {
}
