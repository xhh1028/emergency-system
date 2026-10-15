package com.metro.emergency.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 用户数据访问层。当前仅包含登录需要的最小查询。
 */
@Repository
public class UserRepository {

    private final JdbcTemplate jdbcTemplate;

    public UserRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Optional<UserAccount> findByUsername(String username) {
        // 登录账号使用员工手机号（sys_user.phone）。
        String sql = """
                SELECT u.id, u.phone AS username, u.password AS password_hash,
                       u.real_name AS nickname, r.role_en_name, r.role_name,
                       COALESCE(p.post_name, '') AS post_name,
                       u.on_duty_status, u.station_id,
                       COALESCE(s.station_name, '') AS station_name
                FROM sys_user u
                JOIN sys_role r ON r.id = u.role_id
                LEFT JOIN station_post p ON p.id = u.post_id
                LEFT JOIN station s ON s.id = u.station_id
                WHERE u.phone = ?
                LIMIT 1
                """;

        return jdbcTemplate.query(sql, (resultSet, rowNumber) -> new UserAccount(
                resultSet.getLong("id"),
                resultSet.getString("username"),
                resultSet.getString("password_hash"),
                resultSet.getString("nickname"),
                mapRole(resultSet.getString("role_en_name")),
                resultSet.getString("role_name"),
                mapSubRole(resultSet.getString("post_name")),
                valueOrEmpty(resultSet.getString("post_name")),
                "https://api.dicebear.com/7.x/bottts/svg?seed=" + resultSet.getString("username"),
                !"DISABLED".equalsIgnoreCase(resultSet.getString("on_duty_status")),
                resultSet.getObject("station_id", Long.class),
                resultSet.getString("station_name")
        ), username).stream().findFirst();
    }

    public int updatePasswordHash(String username, String passwordHash) {
        return jdbcTemplate.update(
                "UPDATE sys_user SET password = ? WHERE phone = ?",
                passwordHash, username);
    }

    public Map<String, Object> findRealtimeProfile(long userId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT r.role_en_name role_name,u.station_id
                FROM sys_user u JOIN sys_role r ON r.id=u.role_id WHERE u.id=?
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("role", rs.getString("role_name"));
            item.put("stationId", rs.getObject("station_id", Long.class));
            return item;
        }, userId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /** 查询当前账号在用户、角色、岗位和车站表中的真实个人资料。 */
    public Map<String, Object> findProfile(long userId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT u.id,u.phone,u.real_name,u.on_duty_status,u.station_id,
                       r.role_en_name,r.role_name,COALESCE(p.post_name,'') post_name,
                       COALESCE(s.station_name,'') station_name,s.line_name
                FROM sys_user u JOIN sys_role r ON r.id=u.role_id
                LEFT JOIN station_post p ON p.id=u.post_id
                LEFT JOIN station s ON s.id=u.station_id
                WHERE u.id=?
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("phone", rs.getString("phone"));
            item.put("realName", rs.getString("real_name"));
            item.put("role", mapRole(rs.getString("role_en_name")));
            item.put("roleName", rs.getString("role_name"));
            item.put("postName", valueOrEmpty(rs.getString("post_name")));
            item.put("status", rs.getString("on_duty_status"));
            item.put("stationId", rs.getObject("station_id", Long.class));
            item.put("stationName", valueOrEmpty(rs.getString("station_name")));
            item.put("lineName", rs.getObject("line_name", Integer.class));
            return item;
        }, userId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    private String mapRole(String roleEnName) {
        return switch (roleEnName == null ? "" : roleEnName.toUpperCase()) {
            case "STATION" -> "station";
            case "DISPATCH" -> "dispatch_center";
            case "FRONT" -> "field";
            case "SECURITY" -> "support";
            default -> roleEnName == null ? "" : roleEnName.toLowerCase();
        };
    }

    private String mapSubRole(String postName) {
        if (postName == null) return "";
        return switch (postName) {
            case "安保人员" -> "security";
            case "医护人员" -> "medical";
            case "物资库房管理员" -> "warehouse";
            case "清洁人员" -> "cleaner";
            default -> "";
        };
    }

    private String valueOrEmpty(String value) {
        return value == null ? "" : value;
    }
}
