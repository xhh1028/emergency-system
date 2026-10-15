package com.metro.emergency.repository;

import com.metro.emergency.dto.EventReportResponse;
import com.metro.emergency.dto.PageResponse;
import com.metro.emergency.service.AiAssessmentService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 事件、任务与个人历史记录的数据访问层。 */
@Repository
public class EventRepository {

    private final JdbcTemplate jdbcTemplate;

    public EventRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Long findStationId(long userId) {
        return jdbcTemplate.query(
                "SELECT station_id FROM sys_user WHERE id=?",
                rs -> rs.next() ? rs.getObject(1, Long.class) : null,
                userId);
    }

    public EventReportResponse insertEvent(String eventNo, String type, String preLevel, long stationId,
                                           String eventTitle, String faultyDevice, String description,
                                           String imageUrls, long reporterId, boolean isEmergency) {
        var keyHolder = new org.springframework.jdbc.support.GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO event(event_no,event_type,pre_level,station_id,event_title,faulty_device,describe_text,img_url,
                                      reporter_id,event_status,create_time,final_event_level,is_up_report,is_emergency)
                    VALUES(?,?,?,?,?,?,?,?,?,'PENDING',CURRENT_TIMESTAMP,'UNCONFIRMED',0,?)
                    """, Statement.RETURN_GENERATED_KEYS);
            statement.setString(1, eventNo);
            statement.setString(2, type);
            statement.setString(3, preLevel);
            statement.setLong(4, stationId);
            statement.setString(5, eventTitle);
            statement.setString(6, faultyDevice);
            statement.setString(7, description);
            statement.setString(8, imageUrls);
            statement.setLong(9, reporterId);
            statement.setBoolean(10, isEmergency);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) {
            throw new IllegalStateException("事件已保存，但未能取得事件编号");
        }
        return new EventReportResponse(key.longValue(), eventNo, "PENDING");
    }

    /** 查询本人发起的事件（用于撤回前置校验：确认归属与当前状态）。 */
    public Map<String, Object> findMyEvent(long eventId, long reporterId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT e.id,e.event_no,e.event_status,e.is_withdraw
                FROM event e WHERE e.id=? AND e.reporter_id=?
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventNo", rs.getString("event_no"));
            item.put("status", rs.getString("event_status"));
            item.put("isWithdraw", rs.getInt("is_withdraw") == 1);
            return item;
        }, eventId, reporterId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /** 事件撤回（逻辑删除）：仅本人发起、待处理状态、未撤回的事件可撤回。 */
    public int withdrawEvent(long eventId, long reporterId) {
        return jdbcTemplate.update("""
                UPDATE event SET is_withdraw=1
                WHERE id=? AND reporter_id=? AND event_status='PENDING' AND is_withdraw=0
                """, eventId, reporterId);
    }

    /** 一线补全信息后重新提交被驳回的事件，状态改为 CONFIRMED。 */
    public int resubmitEvent(long eventId, long reporterId, String eventTitle, String faultyDevice,
                             String description, String imageUrls) {
        return jdbcTemplate.update("""
                UPDATE event SET event_title=?,faulty_device=?,describe_text=?,img_url=?,
                                 event_status='CONFIRMED',reject_reason=NULL,reject_time=NULL
                WHERE id=? AND reporter_id=? AND event_status='REJECTED'
                """, eventTitle, faultyDevice, description, imageUrls, eventId, reporterId);
    }

    /** 写入事件流转日志（复用既有 event_log 表结构），留存紧急标记、跳过驳回、AI 研判、人工定级等过程。 */
    public int insertEventLog(long eventId, String operateType, String aiSuggestLevel, String finalEventLevel,
                              String operateDesc, Long operatorId) {
        return jdbcTemplate.update("""
                INSERT INTO event_log(event_id,operate_user_id,operate_type,ai_suggest_level,final_event_level,operate_desc)
                VALUES(?,?,?,?,?,?)
                """, eventId, operatorId, operateType, aiSuggestLevel, finalEventLevel, operateDesc);
    }

    /** 保存自动研判等级，供车站管理员进入待办后直接复核。 */
    public int updateAiAssessment(long eventId, AiAssessmentService.Assessment assessment) {
        return jdbcTemplate.update(
                "UPDATE event SET ai_predict_level=?,ai_reason=?,ai_source=?,ai_plan=? WHERE id=?",
                assessment.level(), assessment.reason(), assessment.source(), assessment.plan(), eventId);
    }

    public PageResponse<Map<String, Object>> findMyEvents(long reporterId, String keyword,
                                                           LocalDateTime start, LocalDateTime end,
                                                           int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE e.reporter_id=?");
        args.add(reporterId);
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (e.event_no LIKE ? OR e.event_title LIKE ? OR e.faulty_device LIKE ? OR e.event_type LIKE ? OR e.describe_text LIKE ?)");
            String like = "%" + keyword.trim() + "%";
            args.add(like);
            args.add(like);
            args.add(like);
            args.add(like);
            args.add(like);
        }
        if (start != null) {
            where.append(" AND e.create_time>=?");
            args.add(start);
        }
        if (end != null) {
            where.append(" AND e.create_time<=?");
            args.add(end);
        }

        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM event e" + where, Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT e.id,e.event_no,e.event_title AS title,e.faulty_device,
                               e.event_type,s.station_name,e.event_status,e.create_time,
                               e.describe_text,e.img_url,e.pre_level,e.ai_predict_level,e.ai_reason,e.ai_source,e.ai_plan,
                               e.is_emergency,e.reject_reason,e.is_withdraw
                        FROM event e JOIN station s ON s.id=e.station_id
                        """ + where + " ORDER BY e.create_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", rs.getLong("id"));
                    item.put("eventNo", rs.getString("event_no"));
                    item.put("title", rs.getString("title"));
                    item.put("faultyDevice", value(rs.getString("faulty_device")));
                    item.put("eventType", rs.getString("event_type"));
                    item.put("stationName", rs.getString("station_name"));
                    item.put("status", rs.getString("event_status"));
                    item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
                    item.put("description", value(rs.getString("describe_text")));
                    item.put("imageUrls", value(rs.getString("img_url")));
                    item.put("preLevel", rs.getString("pre_level"));
                    item.put("aiLevel", value(rs.getString("ai_predict_level")));
                    item.put("aiReason", value(rs.getString("ai_reason")));
                    item.put("aiSource", value(rs.getString("ai_source")));
                    item.put("aiPlan", value(rs.getString("ai_plan")));
                    item.put("isEmergency", rs.getInt("is_emergency") == 1);
                    item.put("rejectReason", value(rs.getString("reject_reason")));
                    item.put("isWithdraw", rs.getInt("is_withdraw") == 1);
                    return item;
                }, listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    public PageResponse<Map<String, Object>> findCompletedTasks(long executorId, String keyword,
                                                                 LocalDateTime start, LocalDateTime end,
                                                                 int page, int size) {
        List<Object> args = new ArrayList<>();
        StringBuilder where = new StringBuilder(" WHERE t.executor_id=? AND t.task_status='COMPLETED'");
        args.add(executorId);
        if (keyword != null && !keyword.isBlank()) {
            where.append(" AND (t.task_content LIKE ? OR e.event_type LIKE ?)");
            String like = "%" + keyword.trim() + "%";
            args.add(like);
            args.add(like);
        }
        if (start != null) {
            where.append(" AND f.completed_time>=?");
            args.add(start);
        }
        if (end != null) {
            where.append(" AND f.completed_time<=?");
            args.add(end);
        }

        String from = """
                FROM task t JOIN event e ON e.id=t.event_id JOIN station s ON s.id=t.station_id
                LEFT JOIN (SELECT task_id,MAX(create_time) completed_time FROM feedback GROUP BY task_id) f
                  ON f.task_id=t.id
                """;
        Long total = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) " + from + where, Long.class, args.toArray());
        List<Object> listArgs = new ArrayList<>(args);
        listArgs.add(size);
        listArgs.add((page - 1) * size);
        List<Map<String, Object>> list = jdbcTemplate.query("""
                        SELECT t.id,CONCAT('TK-',LPAD(t.id,8,'0')) task_no,t.task_content,t.task_source,
                               e.event_type,s.station_name,t.create_time,f.completed_time,t.evaluation,
                               TIMESTAMPDIFF(MINUTE,t.create_time,f.completed_time) duration_minutes
                        """ + from + where + " ORDER BY f.completed_time DESC LIMIT ? OFFSET ?",
                (rs, row) -> {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", rs.getLong("id"));
                    item.put("taskNo", rs.getString("task_no"));
                    item.put("taskName", value(rs.getString("task_content")));
                    item.put("source", value(rs.getString("task_source")));
                    item.put("type", value(rs.getString("event_type")));
                    item.put("stationName", value(rs.getString("station_name")));
                    item.put("createTime", rs.getTimestamp("create_time").toLocalDateTime());
                    item.put("completedTime", rs.getTimestamp("completed_time") == null
                            ? "" : rs.getTimestamp("completed_time").toLocalDateTime());
                    item.put("durationMinutes", rs.getObject("duration_minutes") == null
                            ? 0 : rs.getInt("duration_minutes"));
                    item.put("evaluation", value(rs.getString("evaluation")));
                    return item;
                }, listArgs.toArray());
        return new PageResponse<>(list, total == null ? 0 : total, page, size);
    }

    private String value(String value) {
        return value == null ? "" : value;
    }
}
