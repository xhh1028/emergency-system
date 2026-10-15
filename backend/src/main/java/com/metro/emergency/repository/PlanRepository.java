package com.metro.emergency.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 应急预案数据访问层，读取既有 pre_plan 表。
 */
@Repository
public class PlanRepository {

    private final JdbcTemplate jdbcTemplate;

    public PlanRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<Map<String, Object>> findPlans(String keyword, String level, String type) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (keyword != null && !keyword.isBlank()) {
            String like = "%" + keyword.trim() + "%";
            where.append(" AND (plan_name LIKE ? OR plan_content LIKE ? OR match_event_type LIKE ?)");
            args.add(like);
            args.add(like);
            args.add(like);
        }
        if (level != null && !level.isBlank()) {
            where.append(" AND event_level = ?");
            args.add(level.trim());
        }
        if (type != null && !type.isBlank()) {
            where.append(" AND match_event_type = ?");
            args.add(type.trim());
        }
        String sql = """
                SELECT id, plan_name, event_level, match_event_type, plan_content, update_time
                FROM pre_plan
                """ + where + " ORDER BY update_time DESC, id ASC";
        return jdbcTemplate.query(sql, (rs, row) -> planMap(rs), args.toArray());
    }

    public Optional<Map<String, Object>> findPlan(long id) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id, plan_name, event_level, match_event_type, plan_content, update_time
                FROM pre_plan WHERE id = ?
                """, (rs, row) -> planMap(rs), id);
        return rows.stream().findFirst();
    }

    private Map<String, Object> planMap(ResultSet rs) throws SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", rs.getLong("id"));
        item.put("name", rs.getString("plan_name"));
        item.put("eventLevel", rs.getString("event_level"));
        item.put("matchEventType", rs.getString("match_event_type"));
        item.put("content", rs.getString("plan_content"));
        var updateTime = rs.getTimestamp("update_time");
        item.put("updateTime", updateTime == null ? null : updateTime.toLocalDateTime()
                .toString().replace("T", " ").substring(0, 19));
        return item;
    }
}
