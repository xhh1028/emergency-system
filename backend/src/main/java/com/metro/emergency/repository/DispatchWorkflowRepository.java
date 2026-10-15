package com.metro.emergency.repository;

import com.metro.emergency.dto.PageResponse;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 调度事件确认、指令下发和全线任务监督的数据访问层。 */
@Repository
public class DispatchWorkflowRepository {
    private final JdbcTemplate jdbcTemplate;

    public DispatchWorkflowRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public String findRole(long userId) {
        List<String> roles = jdbcTemplate.query("""
                SELECT r.role_en_name FROM sys_user u JOIN sys_role r ON r.id=u.role_id WHERE u.id=?
                """, (rs, row) -> rs.getString(1), userId);
        return roles.isEmpty() ? null : roles.get(0);
    }

    public PageResponse<Map<String, Object>> findEvents(String status, String keyword, int page, int size) {
        List<Object> args = new ArrayList<>();
        // 已撤回的事件从待办列表隐藏；纳入 PENDING 待处理状态（撤回前置条件）
        StringBuilder where = new StringBuilder(
                " WHERE e.event_status IN ('PENDING','PENDING_ASSIGN','STATION_HANDLE','REPORTED_TO_DISPATCH','FINISHED')"
                        + " AND e.is_withdraw=0");
        if (status != null && !status.isBlank() && !"ALL".equalsIgnoreCase(status)) {
            where.append(" AND e.event_status=?"); args.add(status.toUpperCase());
        }
        if (keyword != null && !keyword.isBlank()) {
            String like = "%" + keyword.trim() + "%";
            where.append(" AND (e.event_no LIKE ? OR e.describe_text LIKE ? OR s.station_name LIKE ? OR u.real_name LIKE ?)");
            args.add(like); args.add(like); args.add(like); args.add(like);
        }
        String from = """
                FROM event e JOIN station s ON s.id=e.station_id JOIN sys_user u ON u.id=e.reporter_id
                """;
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) " + from + where, Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args); listArgs.add(size); listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT e.id,e.event_no,e.event_title,e.faulty_device,e.event_type,e.pre_level,e.ai_predict_level,
                               e.ai_reason,e.ai_source,e.ai_plan,e.final_event_level,e.dispatch_confirm,e.dispatch_confirm_time,
                               e.event_status,e.describe_text,e.img_url,e.create_time,e.is_up_report,e.station_id,
                               e.is_withdraw,u.id reporter_id,
                               s.station_name,s.line_name,u.real_name reporter_name,
                               (SELECT COUNT(*) FROM task t WHERE t.event_id=e.id) task_count,
                               (SELECT COUNT(*) FROM task t WHERE t.event_id=e.id AND t.task_status='COMPLETED') completed_count
                        """ + from + where + " ORDER BY e.create_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> eventMap(rs), listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public Map<String, Object> findEvent(long eventId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT e.id,e.event_no,e.event_title,e.faulty_device,e.event_type,e.pre_level,e.ai_predict_level,
                       e.ai_reason,e.ai_source,e.ai_plan,e.final_event_level,e.dispatch_confirm,e.dispatch_confirm_time,
                       e.event_status,e.describe_text,e.img_url,e.create_time,e.is_up_report,e.station_id,
                       e.is_withdraw,u.id reporter_id,
                       s.station_name,s.line_name,u.real_name reporter_name,
                       (SELECT COUNT(*) FROM task t WHERE t.event_id=e.id) task_count,
                       (SELECT COUNT(*) FROM task t WHERE t.event_id=e.id AND t.task_status='COMPLETED') completed_count
                FROM event e JOIN station s ON s.id=e.station_id JOIN sys_user u ON u.id=e.reporter_id
                WHERE e.id=? AND e.event_status IN ('PENDING','PENDING_ASSIGN','STATION_HANDLE','REPORTED_TO_DISPATCH','FINISHED')
                """, (rs, row) -> eventMap(rs), eventId);
        if (rows.isEmpty()) return null;
        Map<String, Object> event = rows.get(0);
        event.put("plans", findPlans(String.valueOf(event.get("eventType")), String.valueOf(event.get("aiLevel"))));
        event.put("commands", jdbcTemplate.query("""
                SELECT c.id,c.command_content,c.command_time,c.read_status,u.real_name sender_name
                FROM dispatch_command c JOIN sys_user u ON u.id=c.send_user_id
                WHERE c.event_id=? ORDER BY c.command_time DESC
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id")); item.put("content", rs.getString("command_content"));
            item.put("sendTime", rs.getTimestamp("command_time").toLocalDateTime());
            item.put("read", rs.getInt("read_status") == 1); item.put("sender", rs.getString("sender_name"));
            return item;
        }, eventId));
        event.put("tasks", findEventTasks(eventId));
        return event;
    }

    public PageResponse<Map<String, Object>> findArchive(String keyword, String level, Integer year,
                                                          int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE e.event_status='FINISHED'");
        if (keyword != null && !keyword.isBlank()) {
            String like = "%" + keyword.trim() + "%";
            where.append(" AND (e.event_no LIKE ? OR e.describe_text LIKE ? OR s.station_name LIKE ? OR u.real_name LIKE ?)");
            args.add(like); args.add(like); args.add(like); args.add(like);
        }
        if (level != null && !level.isBlank() && !"ALL".equalsIgnoreCase(level)) {
            where.append(" AND e.final_event_level=?");
            args.add(level.toUpperCase());
        }
        if (year != null) {
            where.append(" AND YEAR(e.create_time)=?");
            args.add(year);
        }
        String from = """
                FROM event e JOIN station s ON s.id=e.station_id JOIN sys_user u ON u.id=e.reporter_id
                """;
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) " + from + where,
                Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT e.id,e.event_no,e.event_type,e.final_event_level,e.describe_text,e.create_time,
                               s.station_name,s.line_name,u.real_name reporter_name,
                               (SELECT COUNT(*) FROM task t WHERE t.event_id=e.id) task_count,
                               (SELECT COUNT(*) FROM task t WHERE t.event_id=e.id AND t.task_status='COMPLETED') completed_count,
                               (SELECT COUNT(*) FROM dispatch_command c WHERE c.event_id=e.id) command_count,
                               COALESCE(e.close_time,e.create_time) closed_time
                        """ + from + where + " ORDER BY closed_time DESC,e.id DESC LIMIT ? OFFSET ?",
                (rs, row) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", rs.getLong("id"));
                    item.put("eventNo", rs.getString("event_no"));
                    item.put("eventType", rs.getString("event_type"));
                    item.put("finalLevel", value(rs.getString("final_event_level")));
                    item.put("description", value(rs.getString("describe_text")));
                    item.put("stationName", rs.getString("station_name"));
                    item.put("lineName", rs.getInt("line_name"));
                    item.put("reporterName", rs.getString("reporter_name"));
                    item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
                    item.put("closedTime", rs.getTimestamp("closed_time").toLocalDateTime());
                    item.put("taskCount", rs.getInt("task_count"));
                    item.put("completedCount", rs.getInt("completed_count"));
                    item.put("commandCount", rs.getInt("command_count"));
                    return item;
                }, listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public List<Integer> findArchiveYears() {
        return jdbcTemplate.query("""
                SELECT DISTINCT YEAR(create_time) archive_year FROM event
                WHERE event_status='FINISHED' ORDER BY archive_year DESC
                """, (rs, row) -> rs.getInt("archive_year"));
    }

    private List<Map<String, Object>> findEventTasks(long eventId) {
        List<Map<String, Object>> tasks = jdbcTemplate.query("""
                SELECT t.id,t.task_source,t.task_content,t.task_status,t.create_time,t.deadline,t.evaluation,
                       u.real_name executor_name,COALESCE(p.post_name,'') post_name
                FROM task t JOIN sys_user u ON u.id=t.executor_id
                LEFT JOIN station_post p ON p.id=u.post_id
                WHERE t.event_id=? ORDER BY t.create_time
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("taskNo", "TK-" + String.format("%08d", rs.getLong("id")));
            item.put("source", rs.getString("task_source"));
            item.put("content", rs.getString("task_content"));
            item.put("status", rs.getString("task_status"));
            item.put("evaluation", value(rs.getString("evaluation")));
            item.put("executorName", rs.getString("executor_name"));
            item.put("postName", rs.getString("post_name"));
            item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
            item.put("deadline", rs.getTimestamp("deadline") == null ? "" : rs.getTimestamp("deadline").toLocalDateTime());
            return item;
        }, eventId);
        for (Map<String, Object> task : tasks) {
            long taskId = ((Number) task.get("id")).longValue();
            task.put("feedback", jdbcTemplate.query("""
                    SELECT f.id,f.feedback_text,f.feedback_img,f.create_time,u.real_name operator_name
                    FROM feedback f JOIN sys_user u ON u.id=f.operator_id
                    WHERE f.task_id=? ORDER BY f.create_time
                    """, (rs, row) -> {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("id", rs.getLong("id"));
                item.put("text", value(rs.getString("feedback_text")));
                item.put("imageUrls", value(rs.getString("feedback_img")));
                item.put("operatorName", rs.getString("operator_name"));
                item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
                return item;
            }, taskId));
        }
        return tasks;
    }

    private List<Map<String, Object>> findPlans(String eventType, String level) {
        String databaseType = switch (eventType) {
            case "DEVICE_FAILURE" -> "设备类故障";
            case "FIRE" -> "火灾火情事件";
            case "PASSENGER" -> "乘客人员事件";
            case "TRACK_OPERATION" -> "轨道异物及行车险情";
            case "CROWD_SECURITY" -> "大客流与治安事件";
            case "DISASTER_ENVIRONMENT" -> "灾害与环境事件";
            default -> "其他突发事件";
        };
        String databaseLevel = switch (level) {
            case "EXTREMELY_SERIOUS" -> "一级";
            case "SERIOUS" -> "二级";
            default -> "三级";
        };
        return jdbcTemplate.query("""
                SELECT id,plan_name,event_level,plan_content FROM pre_plan
                WHERE match_event_type=? ORDER BY CASE WHEN event_level=? THEN 0 ELSE 1 END,id LIMIT 5
                """, (rs, row) -> Map.of(
                "id", rs.getLong("id"), "name", rs.getString("plan_name"),
                "level", rs.getString("event_level"), "content", rs.getString("plan_content")
        ), databaseType, databaseLevel);
    }

    public int confirmEvent(long eventId) {
        return jdbcTemplate.update("""
                UPDATE event SET dispatch_confirm=1,dispatch_confirm_time=CURRENT_TIMESTAMP
                WHERE id=? AND event_status='REPORTED_TO_DISPATCH' AND dispatch_confirm=0
                """, eventId);
    }

    public int insertCommand(long eventId, long senderId, long stationId, String content) {
        return jdbcTemplate.update("""
                INSERT INTO dispatch_command(event_id,send_user_id,receive_station_id,command_content,command_time,read_status)
                VALUES(?,?,?,?,CURRENT_TIMESTAMP,0)
                """, eventId, senderId, stationId, content);
    }

    public int setFinalLevel(long eventId, String finalLevel) {
        return jdbcTemplate.update("""
                UPDATE event SET final_event_level=?
                WHERE id=? AND event_status='REPORTED_TO_DISPATCH' AND dispatch_confirm=1
                """, finalLevel, eventId);
    }

    public int closeEvent(long eventId, String finalLevel) {
        return jdbcTemplate.update("UPDATE event SET event_status='FINISHED',final_event_level=?,close_time=CURRENT_TIMESTAMP WHERE id=? AND event_status<>'FINISHED'",
                finalLevel, eventId);
    }

    public PageResponse<Map<String, Object>> findProgress(Long stationId, String status, String keyword,
                                                           int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE 1=1");
        if (stationId != null) { where.append(" AND t.station_id=?"); args.add(stationId); }
        if (status != null && !status.isBlank() && !"ALL".equalsIgnoreCase(status)) {
            if ("OVERDUE".equalsIgnoreCase(status)) where.append(" AND t.task_status<>'COMPLETED' AND t.deadline<CURRENT_TIMESTAMP");
            else { where.append(" AND t.task_status=?"); args.add(status.toUpperCase()); }
        }
        if (keyword != null && !keyword.isBlank()) {
            String like = "%" + keyword.trim() + "%";
            where.append(" AND (t.task_content LIKE ? OR e.event_no LIKE ? OR u.real_name LIKE ? OR s.station_name LIKE ?)");
            args.add(like); args.add(like); args.add(like); args.add(like);
        }
        String from = """
                FROM task t JOIN event e ON e.id=t.event_id JOIN station s ON s.id=t.station_id
                JOIN sys_user u ON u.id=t.executor_id LEFT JOIN station_post p ON p.id=u.post_id
                LEFT JOIN (SELECT task_id,MAX(create_time) latest_feedback FROM feedback GROUP BY task_id) f ON f.task_id=t.id
                """;
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) " + from + where, Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args); listArgs.add(size); listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                SELECT t.id,t.executor_id,t.task_content,t.task_source,t.task_status,t.create_time,t.deadline,t.evaluation,
                       e.event_no,e.event_type,s.id station_id,s.station_name,u.real_name executor_name,
                       COALESCE(p.post_name,'') post_name,f.latest_feedback
                """ + from + where + " ORDER BY t.create_time DESC LIMIT ? OFFSET ?", (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            String raw = rs.getString("task_status");
            var deadline = rs.getTimestamp("deadline") == null ? null : rs.getTimestamp("deadline").toLocalDateTime();
            boolean overdue = deadline != null && deadline.isBefore(java.time.LocalDateTime.now()) && !"COMPLETED".equals(raw);
            item.put("id", rs.getLong("id")); item.put("eventNo", rs.getString("event_no"));
            item.put("executorId", rs.getLong("executor_id"));
            item.put("eventType", rs.getString("event_type")); item.put("content", rs.getString("task_content"));
            item.put("source", rs.getString("task_source")); item.put("stationId", rs.getLong("station_id"));
            item.put("stationName", rs.getString("station_name")); item.put("executorName", rs.getString("executor_name"));
            item.put("postName", rs.getString("post_name")); item.put("rawStatus", raw);
            item.put("status", overdue ? "OVERDUE" : raw);
            item.put("progress", "COMPLETED".equals(raw) ? 100 : "IN_PROGRESS".equals(raw) ? 50 : 0);
            item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
            item.put("deadline", deadline == null ? "" : deadline);
            item.put("latestFeedbackTime", rs.getTimestamp("latest_feedback") == null ? "" : rs.getTimestamp("latest_feedback").toLocalDateTime());
            item.put("evaluation", value(rs.getString("evaluation")));
            return item;
        }, listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public Map<String, Object> findProgressTask(long taskId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id,executor_id,task_status FROM task WHERE id=?
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("executorId", rs.getLong("executor_id"));
            item.put("rawStatus", rs.getString("task_status"));
            return item;
        }, taskId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public int evaluateTask(long taskId, String evaluation) {
        return jdbcTemplate.update("UPDATE task SET evaluation=? WHERE id=? AND task_status='COMPLETED'",
                evaluation, taskId);
    }

    public List<Map<String, Object>> findStations() {
        return jdbcTemplate.query("SELECT id,station_name,line_name FROM station ORDER BY line_name,id", (rs, row) -> Map.of(
                "id", rs.getLong("id"), "name", rs.getString("station_name"), "line", rs.getInt("line_name")
        ));
    }

    /** 调度总览统计、各站活跃事件汇总及最新险情。 */
    public Map<String, Object> findOverview() {
        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, Object> statistics = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) total_events,
                       SUM(CASE WHEN event_status<>'FINISHED' THEN 1 ELSE 0 END) active_events,
                       SUM(CASE WHEN event_status='FINISHED' THEN 1 ELSE 0 END) finished_events,
                       COUNT(DISTINCT CASE WHEN event_status<>'FINISHED' THEN station_id END) alert_stations
                FROM event
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("totalEvents", rs.getLong("total_events"));
            item.put("activeEvents", rs.getLong("active_events"));
            item.put("finishedEvents", rs.getLong("finished_events"));
            item.put("alertStations", rs.getLong("alert_stations"));
            return item;
        });
        result.put("statistics", statistics);
        result.put("stations", jdbcTemplate.query("""
                SELECT s.id,s.station_name,s.line_name,COUNT(e.id) active_event_count,
                       COALESCE(MAX(CASE
                         WHEN e.final_event_level='I_EXTREMELY_SERIOUS' THEN 4
                         WHEN e.final_event_level='II_SERIOUS' OR e.ai_predict_level='EXTREMELY_SERIOUS' THEN 3
                         WHEN e.final_event_level='III_MAJOR' OR e.ai_predict_level='SERIOUS' OR e.pre_level='SERIOUS' THEN 2
                         WHEN e.id IS NOT NULL THEN 1 ELSE 0 END),0) level_rank,
                       SUBSTRING_INDEX(GROUP_CONCAT(e.id ORDER BY
                         CASE WHEN e.final_event_level='I_EXTREMELY_SERIOUS' THEN 4
                              WHEN e.final_event_level='II_SERIOUS' OR e.ai_predict_level='EXTREMELY_SERIOUS' THEN 3
                              WHEN e.final_event_level='III_MAJOR' OR e.ai_predict_level='SERIOUS' OR e.pre_level='SERIOUS' THEN 2
                              ELSE 1 END DESC,e.create_time DESC),',',1) primary_event_id,
                       GROUP_CONCAT(CONCAT(e.event_no,'：',LEFT(COALESCE(e.describe_text,e.event_type),28))
                                    ORDER BY e.create_time DESC SEPARATOR '；') event_briefs
                FROM station s LEFT JOIN event e ON e.station_id=s.id AND e.event_status<>'FINISHED'
                GROUP BY s.id,s.station_name,s.line_name ORDER BY s.line_name,s.id
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            int rank = rs.getInt("level_rank");
            item.put("id", rs.getLong("id"));
            item.put("name", rs.getString("station_name"));
            item.put("line", rs.getInt("line_name"));
            item.put("activeEventCount", rs.getInt("active_event_count"));
            item.put("highestLevel", rank >= 3 ? "EXTREMELY_SERIOUS" : rank == 2 ? "SERIOUS" : rank == 1 ? "GENERAL" : "NONE");
            item.put("primaryEventId", rs.getObject("primary_event_id", Long.class));
            String briefs = rs.getString("event_briefs");
            item.put("brief", briefs == null ? "暂无未闭环事件" : limitBriefs(briefs));
            return item;
        }));
        result.put("latestEvents", jdbcTemplate.query("""
                SELECT e.id,e.event_no,e.event_type,e.event_status,e.describe_text,e.create_time,
                       e.pre_level,e.ai_predict_level,e.final_event_level,s.station_name,s.line_name
                FROM event e JOIN station s ON s.id=e.station_id
                WHERE e.event_status<>'FINISHED'
                ORDER BY e.create_time DESC LIMIT 10
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventNo", rs.getString("event_no"));
            item.put("eventType", rs.getString("event_type"));
            item.put("status", rs.getString("event_status"));
            item.put("description", value(rs.getString("describe_text")));
            item.put("stationName", rs.getString("station_name"));
            item.put("lineName", rs.getInt("line_name"));
            item.put("level", overviewLevel(rs.getString("final_event_level"),
                    rs.getString("ai_predict_level"), rs.getString("pre_level")));
            item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
            return item;
        }));
        return result;
    }

    private String limitBriefs(String value) {
        String[] parts = value.split("；");
        int length = Math.min(parts.length, 3);
        return String.join("；", java.util.Arrays.copyOf(parts, length));
    }

    private String overviewLevel(String finalLevel, String aiLevel, String preLevel) {
        if ("I_EXTREMELY_SERIOUS".equals(finalLevel) || "II_SERIOUS".equals(finalLevel)
                || "EXTREMELY_SERIOUS".equals(aiLevel)) return "EXTREMELY_SERIOUS";
        if ("III_MAJOR".equals(finalLevel) || "SERIOUS".equals(aiLevel) || "SERIOUS".equals(preLevel)) {
            return "SERIOUS";
        }
        return "GENERAL";
    }

    private Map<String, Object> eventMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        String finalLevel = rs.getString("final_event_level");
        item.put("id", rs.getLong("id")); item.put("eventNo", rs.getString("event_no"));
        item.put("title", value(rs.getString("event_title")));
        item.put("faultyDevice", value(rs.getString("faulty_device")));
        item.put("eventType", rs.getString("event_type")); item.put("preLevel", rs.getString("pre_level"));
        item.put("aiLevel", value(rs.getString("ai_predict_level"))); item.put("finalLevel", finalLevel);
        item.put("aiReason", value(rs.getString("ai_reason"))); item.put("aiSource", value(rs.getString("ai_source")));
        item.put("aiPlan", value(rs.getString("ai_plan")));
        item.put("dispatchConfirmed", rs.getInt("dispatch_confirm") == 1);
        item.put("dispatchConfirmTime", rs.getTimestamp("dispatch_confirm_time") == null
                ? "" : rs.getTimestamp("dispatch_confirm_time").toLocalDateTime());
        item.put("status", rs.getString("event_status")); item.put("description", value(rs.getString("describe_text")));
        item.put("imageUrls", value(rs.getString("img_url"))); item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
        item.put("upReported", rs.getInt("is_up_report") == 1); item.put("stationId", rs.getLong("station_id"));
        item.put("stationName", rs.getString("station_name")); item.put("lineName", rs.getInt("line_name"));
        item.put("reporterName", rs.getString("reporter_name")); item.put("taskCount", rs.getInt("task_count"));
        item.put("completedCount", rs.getInt("completed_count"));
        item.put("reporterId", rs.getObject("reporter_id", Long.class));
        item.put("isWithdraw", rs.getInt("is_withdraw") == 1);
        return item;
    }

    private String value(String value) { return value == null ? "" : value; }
}
