package com.metro.emergency.repository;

import com.metro.emergency.dto.PageResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 一线执行与后勤安保人员的本人任务、执行状态和现场反馈数据访问。 */
@Repository
public class TaskExecutionRepository {

    private final JdbcTemplate jdbcTemplate;

    public TaskExecutionRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public String findRole(long userId) {
        List<String> roles = jdbcTemplate.query("""
                SELECT r.role_en_name FROM sys_user u
                JOIN sys_role r ON r.id=u.role_id WHERE u.id=?
                """, (rs, row) -> rs.getString("role_en_name"), userId);
        return roles.isEmpty() ? null : roles.get(0);
    }

    public PageResponse<Map<String, Object>> findMyTasks(long executorId, String status,
                                                          String keyword, int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE t.executor_id=?");
        args.add(executorId);
        if (status != null && !status.isBlank() && !"ALL".equalsIgnoreCase(status)) {
            if ("OVERDUE".equalsIgnoreCase(status)) {
                where.append(" AND t.task_status<>'COMPLETED' AND t.deadline<CURRENT_TIMESTAMP");
            } else {
                where.append(" AND t.task_status=?");
                args.add(status.toUpperCase());
            }
        }
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (t.task_content LIKE ? OR e.event_no LIKE ? OR s.station_name LIKE ?)");
            String like = "%" + keyword.trim() + "%";
            args.add(like);
            args.add(like);
            args.add(like);
        }
        String from = """
                FROM task t JOIN event e ON e.id=t.event_id
                JOIN station s ON s.id=t.station_id
                JOIN sys_user u ON u.id=t.executor_id
                LEFT JOIN station_post p ON p.id=u.post_id
                LEFT JOIN (SELECT task_id,MAX(create_time) latest_feedback FROM feedback GROUP BY task_id) f
                  ON f.task_id=t.id
                """;
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) " + from + where,
                Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT t.id,t.event_id,t.task_source,t.task_content,t.task_status,t.create_time,
                               t.deadline,e.event_no,e.event_type,e.final_event_level,e.describe_text,
                               e.img_url,s.station_name,s.line_name,u.real_name executor_name,
                               COALESCE(p.post_name,'') post_name,f.latest_feedback
                        """ + from + where + " ORDER BY t.create_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> taskMap(rs), listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public Map<String, Object> findMyTask(long taskId, long executorId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                        SELECT t.id,t.event_id,t.task_source,t.task_content,t.task_status,t.create_time,
                               t.deadline,e.event_no,e.event_type,e.final_event_level,e.describe_text,
                               e.img_url,s.station_name,s.line_name,u.real_name executor_name,
                               COALESCE(p.post_name,'') post_name,f.latest_feedback
                        FROM task t JOIN event e ON e.id=t.event_id
                        JOIN station s ON s.id=t.station_id
                        JOIN sys_user u ON u.id=t.executor_id
                        LEFT JOIN station_post p ON p.id=u.post_id
                        LEFT JOIN (SELECT task_id,MAX(create_time) latest_feedback FROM feedback GROUP BY task_id) f
                          ON f.task_id=t.id
                        WHERE t.id=? AND t.executor_id=?
                        """, (rs, row) -> taskMap(rs), taskId, executorId);
        if (rows.isEmpty()) return null;
        Map<String, Object> task = rows.get(0);
        task.put("feedback", findFeedback(taskId));
        return task;
    }

    public int startTask(long taskId, long executorId) {
        return jdbcTemplate.update("""
                UPDATE task SET task_status='IN_PROGRESS'
                WHERE id=? AND executor_id=? AND task_status='PENDING'
                """, taskId, executorId);
    }

    public int completeTask(long taskId, long executorId) {
        return jdbcTemplate.update("""
                UPDATE task SET task_status='COMPLETED'
                WHERE id=? AND executor_id=? AND task_status='IN_PROGRESS'
                """, taskId, executorId);
    }

    public int insertFeedback(long taskId, String text, String imageUrls, long operatorId) {
        return jdbcTemplate.update("""
                INSERT INTO feedback(task_id,feedback_text,feedback_img,operator_id,create_time)
                VALUES(?,?,?,?,CURRENT_TIMESTAMP)
                """, taskId, text, imageUrls, operatorId);
    }

    private List<Map<String, Object>> findFeedback(long taskId) {
        return jdbcTemplate.query("""
                        SELECT f.id,f.feedback_text,f.feedback_img,f.create_time,u.real_name operator_name
                        FROM feedback f JOIN sys_user u ON u.id=f.operator_id
                        WHERE f.task_id=? ORDER BY f.create_time DESC
                        """, (rs, row) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", rs.getLong("id"));
                    item.put("text", value(rs.getString("feedback_text")));
                    item.put("imageUrls", value(rs.getString("feedback_img")));
                    item.put("operatorName", rs.getString("operator_name"));
                    item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
                    return item;
                }, taskId);
    }

    private Map<String, Object> taskMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        String rawStatus = rs.getString("task_status");
        java.sql.Timestamp deadlineValue = rs.getTimestamp("deadline");
        java.time.LocalDateTime deadline = deadlineValue == null ? null : deadlineValue.toLocalDateTime();
        boolean overdue = deadline != null && deadline.isBefore(java.time.LocalDateTime.now())
                && !"COMPLETED".equals(rawStatus);
        item.put("id", rs.getLong("id"));
        item.put("taskNo", "TK-" + String.format("%08d", rs.getLong("id")));
        item.put("eventId", rs.getLong("event_id"));
        item.put("eventNo", rs.getString("event_no"));
        item.put("eventType", rs.getString("event_type"));
        item.put("eventLevel", value(rs.getString("final_event_level")));
        item.put("eventDescription", value(rs.getString("describe_text")));
        item.put("eventImageUrls", value(rs.getString("img_url")));
        item.put("stationName", rs.getString("station_name"));
        item.put("lineName", rs.getString("line_name"));
        item.put("source", rs.getString("task_source"));
        item.put("content", rs.getString("task_content"));
        item.put("executorName", rs.getString("executor_name"));
        item.put("postName", rs.getString("post_name"));
        item.put("status", overdue ? "OVERDUE" : rawStatus);
        item.put("rawStatus", rawStatus);
        item.put("progress", "COMPLETED".equals(rawStatus) ? 100 : "IN_PROGRESS".equals(rawStatus) ? 50 : 0);
        item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
        item.put("deadline", deadline == null ? "" : deadline);
        item.put("latestFeedbackTime", rs.getTimestamp("latest_feedback") == null
                ? "" : rs.getTimestamp("latest_feedback").toLocalDateTime());
        return item;
    }

    private String value(String value) {
        return value == null ? "" : value;
    }
}
