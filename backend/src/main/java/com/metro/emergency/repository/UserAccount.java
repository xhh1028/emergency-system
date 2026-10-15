package com.metro.emergency.repository;

/**
 * 数据库用户记录。
 */
public record UserAccount(
        long id,
        String username,
        String passwordHash,
        String nickname,
        String role,
        String roleLabel,
        String subRole,
        String subRoleLabel,
        String avatar,
        boolean enabled,
        Long stationId,
        String stationName
) {
}
