package com.metro.emergency.repository;

import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.dto.TaskDraft;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 车站事件复核、预案匹配、人员和任务分派数据访问。 */
@Repository
public class StationWorkflowRepository {

    private final JdbcTemplate jdbcTemplate;

    public StationWorkflowRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public UserScope findUserScope(long userId) {
        return jdbcTemplate.query("""
                        SELECT u.station_id,r.role_en_name FROM sys_user u
                        JOIN sys_role r ON r.id=u.role_id WHERE u.id=?
                        """,
                rs -> rs.next()
                        ? new UserScope(rs.getObject("station_id", Long.class), rs.getString("role_en_name"))
                        : null, userId);
    }

    public PageResponse<Map<String, Object>> findStationEvents(long stationId, String status,
                                                                String keyword, int page, int size) {
        List<Object> args = new ArrayList<>();
        // 已撤回的事件从事件待办列表过滤隐藏（where is_withdraw = 0）
        StringBuilder where = new StringBuilder(" WHERE e.station_id=? AND e.is_withdraw=0");
        args.add(stationId);
        if (status != null && !status.isBlank() && !"ALL".equalsIgnoreCase(status)) {
            where.append(" AND e.event_status=?");
            args.add(status);
        }
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (e.event_no LIKE ? OR e.event_type LIKE ? OR e.describe_text LIKE ? OR u.real_name LIKE ?)");
            String like = "%" + keyword.trim() + "%";
            args.add(like);
            args.add(like);
            args.add(like);
            args.add(like);
        }
        Long total = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM event e JOIN sys_user u ON u.id=e.reporter_id
                """ + where, Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT e.id,e.event_no,e.event_title,e.faulty_device,e.event_type,e.pre_level,e.ai_predict_level,
                               e.ai_reason,e.ai_source,e.ai_plan,
                               e.final_event_level,e.event_status,e.describe_text,e.img_url,e.create_time,
                               e.is_up_report,e.is_emergency,e.reject_reason,e.reject_time,
                               u.id reporter_id,u.real_name reporter_name,
                               s.station_name,s.line_name
                        FROM event e JOIN sys_user u ON u.id=e.reporter_id
                        JOIN station s ON s.id=e.station_id
                        """ + where + " ORDER BY e.create_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> eventMap(rs), listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public Map<String, Object> findStationEvent(long eventId, long stationId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                        SELECT e.id,e.event_no,e.event_title,e.faulty_device,e.event_type,e.pre_level,e.ai_predict_level,
                               e.ai_reason,e.ai_source,e.ai_plan,
                               e.final_event_level,e.event_status,e.describe_text,e.img_url,e.create_time,
                               e.is_up_report,e.is_emergency,e.reject_reason,e.reject_time,
                               u.id reporter_id,u.real_name reporter_name,
                               s.station_name,s.line_name
                        FROM event e JOIN sys_user u ON u.id=e.reporter_id
                        JOIN station s ON s.id=e.station_id WHERE e.id=? AND e.station_id=?
                        """, (rs, row) -> eventMap(rs), eventId, stationId);
        if (rows.isEmpty()) return null;
        Map<String, Object> event = rows.get(0);
        event.put("plans", findPlans(
                String.valueOf(event.get("eventType")),
                String.valueOf(event.get("aiLevel"))));
        return event;
    }

    public int decide(long eventId, long stationId, String level, String status, boolean upReport) {
        return jdbcTemplate.update("""
                UPDATE event SET final_event_level=?,event_status=?,is_up_report=?
                WHERE id=? AND station_id=?
                """, level, status, upReport ? 1 : 0, eventId, stationId);
    }

    /** 普通险情待处理事件：车站管理员驳回退回一线补全信息。紧急险情禁止驳回。 */
    public int rejectEvent(long eventId, long stationId, String reason) {
        return jdbcTemplate.update("""
                UPDATE event SET event_status='REJECTED',reject_reason=?,reject_time=CURRENT_TIMESTAMP
                WHERE id=? AND station_id=? AND is_emergency=0 AND event_status='PENDING'
                """, reason, eventId, stationId);
    }

    /** 写入事件流转日志（复用既有 event_log 表结构），留存紧急标记、跳过驳回、AI 研判、人工定级等过程。 */
    public int insertEventLog(long eventId, String operateType, String aiSuggestLevel, String finalEventLevel,
                              String operateDesc, Long operatorId) {
        return jdbcTemplate.update("""
                INSERT INTO event_log(event_id,operate_user_id,operate_type,ai_suggest_level,final_event_level,operate_desc)
                VALUES(?,?,?,?,?,?)
                """, eventId, operatorId, operateType, aiSuggestLevel, finalEventLevel, operateDesc);
    }

    public List<Map<String, Object>> findPersonnel(long stationId) {
        return jdbcTemplate.query("""
                        SELECT u.id,u.real_name,u.phone,u.on_duty_status,r.role_name,r.role_en_name,
                               u.post_id,COALESCE(p.post_name,'') post_name
                        FROM sys_user u JOIN sys_role r ON r.id=u.role_id
                        LEFT JOIN station_post p ON p.id=u.post_id
                        WHERE u.station_id=? AND r.role_en_name IN ('FRONT','SECURITY')
                        ORDER BY r.role_en_name,p.post_name,u.real_name
                        """, (rs, row) -> personnelMap(rs), stationId);
    }

    public List<Map<String, Object>> findPersonnelPosts() {
        return jdbcTemplate.query("""
                        SELECT p.id,p.post_name,r.role_en_name
                        FROM station_post p JOIN sys_role r ON r.id=p.role_id
                        WHERE r.role_en_name IN ('FRONT','SECURITY')
                        ORDER BY r.role_en_name,p.id
                        """, (rs, row) -> Map.of(
                "id", rs.getInt("id"),
                "name", rs.getString("post_name"),
                "role", rs.getString("role_en_name")
        ));
    }

    public Integer findRoleId(String role) {
        List<Integer> ids = jdbcTemplate.query(
                "SELECT id FROM sys_role WHERE role_en_name=?",
                (rs, row) -> rs.getInt("id"), role);
        return ids.isEmpty() ? null : ids.get(0);
    }

    public boolean postMatchesRole(int postId, int roleId) {
        Long count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM station_post WHERE id=? AND role_id=?",
                Long.class, postId, roleId);
        return count != null && count == 1;
    }

    public boolean phoneExists(String phone, Long excludedId) {
        Long count = excludedId == null
                ? jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE phone=?", Long.class, phone)
                : jdbcTemplate.queryForObject("SELECT COUNT(*) FROM sys_user WHERE phone=? AND id<>?",
                Long.class, phone, excludedId);
        return count != null && count > 0;
    }

    public long insertPersonnel(long stationId, String realName, String phone, String passwordHash,
                                int roleId, int postId, String status) {
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            var statement = connection.prepareStatement("""
                    INSERT INTO sys_user(real_name,phone,password,role_id,post_id,station_id,on_duty_status)
                    VALUES(?,?,?,?,?,?,?)
                    """, java.sql.Statement.RETURN_GENERATED_KEYS);
            statement.setString(1, realName);
            statement.setString(2, phone);
            statement.setString(3, passwordHash);
            statement.setInt(4, roleId);
            statement.setInt(5, postId);
            statement.setLong(6, stationId);
            statement.setString(7, status);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("人员已保存，但未能取得人员编号");
        return key.longValue();
    }

    public int updatePersonnel(long id, long stationId, String realName, String phone,
                               int roleId, int postId, String status) {
        return jdbcTemplate.update("""
                UPDATE sys_user SET real_name=?,phone=?,role_id=?,post_id=?,on_duty_status=?
                WHERE id=? AND station_id=? AND role_id IN
                  (SELECT id FROM sys_role WHERE role_en_name IN ('FRONT','SECURITY'))
                """, realName, phone, roleId, postId, status, id, stationId);
    }

    public int resetPersonnelPassword(long id, long stationId, String passwordHash) {
        return jdbcTemplate.update("""
                UPDATE sys_user SET password=? WHERE id=? AND station_id=? AND role_id IN
                  (SELECT id FROM sys_role WHERE role_en_name IN ('FRONT','SECURITY'))
                """, passwordHash, id, stationId);
    }

    public Map<String, Object> findPersonnelById(long id, long stationId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                        SELECT u.id,u.real_name,u.phone,u.on_duty_status,r.role_name,r.role_en_name,
                               u.post_id,COALESCE(p.post_name,'') post_name
                        FROM sys_user u JOIN sys_role r ON r.id=u.role_id
                        LEFT JOIN station_post p ON p.id=u.post_id
                        WHERE u.id=? AND u.station_id=? AND r.role_en_name IN ('FRONT','SECURITY')
                        """, (rs, row) -> personnelMap(rs), id, stationId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public PageResponse<Map<String, Object>> findCommands(long stationId, String status,
                                                           String keyword, int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE c.receive_station_id=?");
        args.add(stationId);
        if ("UNREAD".equalsIgnoreCase(status)) where.append(" AND c.read_status=0");
        if ("READ".equalsIgnoreCase(status)) where.append(" AND c.read_status=1");
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (c.command_content LIKE ? OR e.event_no LIKE ? OR sender.real_name LIKE ?)");
            String like = "%" + keyword.trim() + "%";
            args.add(like);
            args.add(like);
            args.add(like);
        }
        String from = """
                FROM dispatch_command c JOIN sys_user sender ON sender.id=c.send_user_id
                LEFT JOIN event e ON e.id=c.event_id
                """;
        Long total = jdbcTemplate.queryForObject("SELECT COUNT(*) " + from + where,
                Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT c.id,c.event_id,c.command_content,c.command_time,c.read_status,
                               c.receive_user_id,sender.real_name sender_name,e.event_no,e.event_type
                        """ + from + where + " ORDER BY c.command_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> commandMap(rs), listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public Map<String, Object> findCommand(long commandId, long stationId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                        SELECT c.id,c.event_id,c.command_content,c.command_time,c.read_status,
                               c.receive_user_id,sender.real_name sender_name,e.event_no,e.event_type
                        FROM dispatch_command c JOIN sys_user sender ON sender.id=c.send_user_id
                        LEFT JOIN event e ON e.id=c.event_id
                        WHERE c.id=? AND c.receive_station_id=?
                        """, (rs, row) -> commandMap(rs), commandId, stationId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public int signCommand(long commandId, long stationId, long userId) {
        return jdbcTemplate.update("""
                UPDATE dispatch_command SET read_status=1,receive_user_id=?
                WHERE id=? AND receive_station_id=? AND read_status=0
                """, userId, commandId, stationId);
    }

    public boolean signedCommandMatches(long commandId, long eventId, long stationId) {
        Long count = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM dispatch_command
                WHERE id=? AND event_id=? AND receive_station_id=? AND read_status=1
                """, Long.class, commandId, eventId, stationId);
        return count != null && count == 1;
    }

    public PageResponse<Map<String, Object>> findTaskProgress(long stationId, Long eventId, String status,
                                                               String keyword, int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE t.station_id=?");
        args.add(stationId);
        if (eventId != null) {
            where.append(" AND t.event_id=?");
            args.add(eventId);
        }
        if (status != null && !status.isBlank() && !"ALL".equalsIgnoreCase(status)) {
            if ("OVERDUE".equalsIgnoreCase(status)) {
                where.append(" AND t.task_status<>'COMPLETED' AND t.deadline<CURRENT_TIMESTAMP");
            } else {
                where.append(" AND t.task_status=?");
                args.add(status.toUpperCase());
            }
        }
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (t.task_content LIKE ? OR u.real_name LIKE ? OR e.event_no LIKE ?)");
            String like = "%" + keyword.trim() + "%";
            args.add(like);
            args.add(like);
            args.add(like);
        }
        String from = """
                FROM task t JOIN event e ON e.id=t.event_id
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
                               t.deadline,e.event_no,e.event_type,COALESCE(e.event_title,'') event_title,
                               u.real_name executor_name,
                               COALESCE(p.post_name,'') post_name,f.latest_feedback
                        """ + from + where + " ORDER BY t.create_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> taskMap(rs), listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    /** 查询本站各顶层事件的子任务总进度：finished 子任务数 / 全部子任务总数 ×100%。 */
    public List<Map<String, Object>> findEventProgress(long stationId) {
        return jdbcTemplate.query("""
                        SELECT e.id,e.event_no,e.event_type,COALESCE(e.event_title,'') event_title,
                               CASE
                                   WHEN e.final_event_level IN ('GENERAL','SERIOUS','EXTREMELY_SERIOUS') THEN e.final_event_level
                                   WHEN e.ai_predict_level IN ('GENERAL','SERIOUS','EXTREMELY_SERIOUS') THEN e.ai_predict_level
                                   WHEN e.pre_level IN ('GENERAL','SERIOUS','EXTREMELY_SERIOUS') THEN e.pre_level
                                   ELSE ''
                               END event_level,
                               COUNT(t.id) total_tasks,
                               COALESCE(SUM(CASE WHEN t.task_status='COMPLETED' THEN 1 ELSE 0 END),0) finished_tasks
                        FROM event e
                        LEFT JOIN task t ON t.event_id=e.id AND t.station_id=?
                        WHERE e.station_id=?
                        GROUP BY e.id,e.event_no,e.event_type,e.event_title,
                                 e.final_event_level,e.ai_predict_level,e.pre_level
                        HAVING COUNT(t.id)>0
                        ORDER BY e.create_time DESC
                        """, (rs, row) -> {
                    long total = rs.getLong("total_tasks");
                    long finished = rs.getLong("finished_tasks");
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", rs.getLong("id"));
                    item.put("eventNo", rs.getString("event_no"));
                    item.put("eventType", rs.getString("event_type"));
                    item.put("eventTitle", rs.getString("event_title"));
                    item.put("eventLevel", rs.getString("event_level"));
                    item.put("totalTasks", total);
                    item.put("finishedTasks", finished);
                    item.put("progress", total == 0 ? 0 : (int) Math.round(finished * 100.0 / total));
                    return item;
                }, stationId, stationId);
    }

    public Map<String, Object> findTaskDetail(long taskId, long stationId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                        SELECT t.id,t.event_id,t.task_source,t.task_content,t.task_status,t.create_time,
                               t.deadline,e.event_no,e.event_type,COALESCE(e.event_title,'') event_title,
                               u.real_name executor_name,
                               COALESCE(p.post_name,'') post_name,f.latest_feedback
                        FROM task t JOIN event e ON e.id=t.event_id
                        JOIN sys_user u ON u.id=t.executor_id
                        LEFT JOIN station_post p ON p.id=u.post_id
                        LEFT JOIN (SELECT task_id,MAX(create_time) latest_feedback FROM feedback GROUP BY task_id) f
                          ON f.task_id=t.id
                        WHERE t.id=? AND t.station_id=?
                        """, (rs, row) -> taskMap(rs), taskId, stationId);
        if (rows.isEmpty()) return null;
        Map<String, Object> task = rows.get(0);
        task.put("feedback", jdbcTemplate.query("""
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
                }, taskId));
        return task;
    }

    public boolean executorBelongsToStation(long executorId, long stationId) {
        Long count = jdbcTemplate.queryForObject("""
                SELECT COUNT(*) FROM sys_user u JOIN sys_role r ON r.id=u.role_id
                WHERE u.id=? AND u.station_id=? AND u.on_duty_status='ON_DUTY'
                  AND r.role_en_name IN ('FRONT','SECURITY')
                """, Long.class, executorId, stationId);
        return count != null && count == 1;
    }

    public int insertTask(long eventId, long stationId, String source, TaskDraft task) {
        return jdbcTemplate.update("""
                INSERT INTO task(event_id,station_id,task_source,task_content,executor_id,
                                 task_status,create_time,deadline)
                VALUES(?,?,?,?,?,'PENDING',CURRENT_TIMESTAMP,?)
                """, eventId, stationId, source, task.content().trim(), task.executorId(),
                task.deadline() == null ? null : Timestamp.valueOf(task.deadline()));
    }

    public int markHandling(long eventId, long stationId, String source) {
        return jdbcTemplate.update("""
                UPDATE event SET event_status=CASE WHEN ?='DISPATCH' THEN 'REPORTED_TO_DISPATCH' ELSE 'STATION_HANDLE' END,
                                 is_up_report=CASE WHEN ?='DISPATCH' THEN 1 ELSE 0 END
                WHERE id=? AND station_id=?
                """, source, source, eventId, stationId);
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
                        SELECT id,plan_name,event_level,plan_content
                        FROM pre_plan WHERE match_event_type=?
                        ORDER BY CASE WHEN event_level=? THEN 0 ELSE 1 END,id LIMIT 5
                        """, (rs, row) -> Map.of(
                "id", rs.getLong("id"),
                "name", rs.getString("plan_name"),
                "level", rs.getString("event_level"),
                "content", rs.getString("plan_content")
        ), databaseType, databaseLevel);
    }

    private Map<String, Object> eventMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", rs.getLong("id"));
        item.put("eventNo", rs.getString("event_no"));
        item.put("title", value(rs.getString("event_title")));
        item.put("faultyDevice", value(rs.getString("faulty_device")));
        item.put("eventType", rs.getString("event_type"));
        item.put("reporterLevel", rs.getString("pre_level"));
        item.put("aiLevel", value(rs.getString("ai_predict_level")));
        item.put("aiReason", value(rs.getString("ai_reason")));
        item.put("aiSource", value(rs.getString("ai_source")));
        item.put("aiPlan", value(rs.getString("ai_plan")));
        item.put("finalLevel", value(rs.getString("final_event_level")));
        item.put("status", rs.getString("event_status"));
        item.put("description", value(rs.getString("describe_text")));
        item.put("imageUrls", value(rs.getString("img_url")));
        item.put("reporterName", rs.getString("reporter_name"));
        item.put("stationName", rs.getString("station_name"));
        item.put("lineName", rs.getString("line_name"));
        item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
        item.put("upReported", rs.getInt("is_up_report") == 1);
        item.put("isEmergency", rs.getInt("is_emergency") == 1);
        item.put("rejectReason", value(rs.getString("reject_reason")));
        item.put("rejectTime", rs.getTimestamp("reject_time") == null
                ? "" : rs.getTimestamp("reject_time").toLocalDateTime());
        item.put("reporterId", rs.getObject("reporter_id", Long.class));
        return item;
    }

    private Map<String, Object> commandMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", rs.getLong("id"));
        item.put("eventId", rs.getObject("event_id", Long.class));
        item.put("eventNo", value(rs.getString("event_no")));
        item.put("eventType", value(rs.getString("event_type")));
        item.put("sender", rs.getString("sender_name"));
        item.put("content", rs.getString("command_content"));
        item.put("sendTime", rs.getTimestamp("command_time").toLocalDateTime());
        item.put("read", rs.getInt("read_status") == 1);
        item.put("receiveUserId", rs.getObject("receive_user_id", Long.class));
        return item;
    }

    private Map<String, Object> taskMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        String status = rs.getString("task_status");
        java.time.LocalDateTime deadline = rs.getTimestamp("deadline") == null
                ? null : rs.getTimestamp("deadline").toLocalDateTime();
        boolean overdue = deadline != null && deadline.isBefore(java.time.LocalDateTime.now())
                && !"COMPLETED".equals(status);
        item.put("id", rs.getLong("id"));
        item.put("taskNo", "TK-" + String.format("%08d", rs.getLong("id")));
        item.put("eventId", rs.getLong("event_id"));
        item.put("eventNo", rs.getString("event_no"));
        // 事件标题不冗余存储在 task 表，通过 event_id 联表从顶层 event 表获取
        item.put("eventTitle", value(rs.getString("event_title")));
        item.put("eventType", rs.getString("event_type"));
        item.put("source", rs.getString("task_source"));
        item.put("content", rs.getString("task_content"));
        item.put("executorName", rs.getString("executor_name"));
        item.put("postName", rs.getString("post_name"));
        item.put("status", overdue ? "OVERDUE" : status);
        item.put("rawStatus", status);
        item.put("progress", "COMPLETED".equals(status) ? 100 : "IN_PROGRESS".equals(status) ? 50 : 0);
        item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
        item.put("deadline", deadline == null ? "" : deadline);
        item.put("latestFeedbackTime", rs.getTimestamp("latest_feedback") == null
                ? "" : rs.getTimestamp("latest_feedback").toLocalDateTime());
        return item;
    }

    private Map<String, Object> personnelMap(java.sql.ResultSet rs) throws java.sql.SQLException {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", rs.getLong("id"));
        item.put("name", rs.getString("real_name"));
        item.put("phone", rs.getString("phone"));
        item.put("status", rs.getString("on_duty_status"));
        item.put("role", rs.getString("role_en_name"));
        item.put("roleName", rs.getString("role_name"));
        item.put("postId", rs.getObject("post_id", Integer.class));
        item.put("postName", rs.getString("post_name"));
        return item;
    }

    private String value(String value) {
        return value == null ? "" : value;
    }

    public record UserScope(Long stationId, String role) {
    }
}
