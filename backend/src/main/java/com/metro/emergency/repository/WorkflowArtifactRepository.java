package com.metro.emergency.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 双轨工作流的持久化基础设施。
 *
 * <p>该 repository 只负责保存不可变的答案/证据/审批快照和追加式审计记录，
 * 不负责决定答案是否可执行；规则判断和权限判断由后续 service 完成。</p>
 */
@Repository
public class WorkflowArtifactRepository {

    private final JdbcTemplate jdbcTemplate;

    public WorkflowArtifactRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public long createWorkflowInstance(long eventId, String workflowType, String currentState,
                                       int version, String correlationId, Long createdBy) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO workflow_instance(event_id,workflow_type,current_state,version,correlation_id,created_by)
                    VALUES(?,?,?,?,?,?)
                    """, Statement.RETURN_GENERATED_KEYS);
            statement.setLong(1, eventId);
            statement.setString(2, workflowType);
            statement.setString(3, currentState);
            statement.setInt(4, version);
            statement.setString(5, correlationId);
            if (createdBy == null) statement.setObject(6, null);
            else statement.setLong(6, createdBy);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("工作流实例已保存，但未能取得编号");
        return key.longValue();
    }

    public Map<String, Object> findWorkflowInstance(long workflowId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id,event_id,workflow_type,current_state,version,correlation_id,created_by,created_at,updated_at
                FROM workflow_instance WHERE id=?
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventId", rs.getLong("event_id"));
            item.put("workflowType", rs.getString("workflow_type"));
            item.put("currentState", rs.getString("current_state"));
            item.put("version", rs.getInt("version"));
            item.put("correlationId", rs.getString("correlation_id"));
            item.put("createdBy", rs.getObject("created_by", Long.class));
            item.put("createdAt", rs.getTimestamp("created_at"));
            item.put("updatedAt", rs.getTimestamp("updated_at"));
            return item;
        }, workflowId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public long insertAnswerCandidate(long eventId, Long workflowInstanceId, int answerVersion,
                                      String source, String status, String schemaVersion,
                                      String answerJson, String modelName, String modelVersion,
                                      String promptHash, String knowledgeVersion, Long createdBy) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO answer_candidate(event_id,workflow_instance_id,answer_version,source,status,
                                                  schema_version,answer_json,model_name,model_version,prompt_hash,
                                                  knowledge_version,created_by)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """, Statement.RETURN_GENERATED_KEYS);
            statement.setLong(1, eventId);
            if (workflowInstanceId == null) statement.setObject(2, null);
            else statement.setLong(2, workflowInstanceId);
            statement.setInt(3, answerVersion);
            statement.setString(4, source);
            statement.setString(5, status);
            statement.setString(6, schemaVersion);
            statement.setString(7, answerJson);
            statement.setString(8, modelName);
            statement.setString(9, modelVersion);
            statement.setString(10, promptHash);
            statement.setString(11, knowledgeVersion);
            if (createdBy == null) statement.setObject(12, null);
            else statement.setLong(12, createdBy);
            return statement;
        }, keyHolder);
        Number key = keyHolder.getKey();
        if (key == null) throw new IllegalStateException("候选答案已保存，但未能取得编号");
        return key.longValue();
    }

    public Map<String, Object> findAnswerCandidate(long answerId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id,event_id,workflow_instance_id,answer_version,source,status,schema_version,answer_json,
                       model_name,model_version,prompt_hash,knowledge_version,created_by,created_at
                FROM answer_candidate WHERE id=?
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventId", rs.getLong("event_id"));
            item.put("workflowInstanceId", rs.getObject("workflow_instance_id", Long.class));
            item.put("answerVersion", rs.getInt("answer_version"));
            item.put("source", rs.getString("source"));
            item.put("status", rs.getString("status"));
            item.put("schemaVersion", rs.getString("schema_version"));
            item.put("answerJson", rs.getString("answer_json"));
            item.put("modelName", rs.getString("model_name"));
            item.put("modelVersion", rs.getString("model_version"));
            item.put("promptHash", rs.getString("prompt_hash"));
            item.put("knowledgeVersion", rs.getString("knowledge_version"));
            item.put("createdBy", rs.getObject("created_by", Long.class));
            item.put("createdAt", rs.getTimestamp("created_at"));
            return item;
        }, answerId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public Map<String, Object> findLatestAnswerCandidate(long eventId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id,event_id,workflow_instance_id,answer_version,source,status,schema_version,answer_json,
                       model_name,model_version,prompt_hash,knowledge_version,created_by,created_at
                FROM answer_candidate WHERE event_id=? ORDER BY answer_version DESC LIMIT 1
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventId", rs.getLong("event_id"));
            item.put("workflowInstanceId", rs.getObject("workflow_instance_id", Long.class));
            item.put("answerVersion", rs.getInt("answer_version"));
            item.put("source", rs.getString("source"));
            item.put("status", rs.getString("status"));
            item.put("schemaVersion", rs.getString("schema_version"));
            item.put("answerJson", rs.getString("answer_json"));
            item.put("modelName", rs.getString("model_name"));
            item.put("modelVersion", rs.getString("model_version"));
            item.put("promptHash", rs.getString("prompt_hash"));
            item.put("knowledgeVersion", rs.getString("knowledge_version"));
            item.put("createdBy", rs.getObject("created_by", Long.class));
            item.put("createdAt", rs.getTimestamp("created_at"));
            return item;
        }, eventId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    public Map<String, Object> findLatestApproval(long answerId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id,answer_id,operator_id,operator_role,action,before_snapshot,after_snapshot,
                       reason,approved_at
                FROM approval_record WHERE answer_id=? ORDER BY id DESC LIMIT 1
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("answerId", rs.getLong("answer_id"));
            item.put("operatorId", rs.getLong("operator_id"));
            item.put("operatorRole", rs.getString("operator_role"));
            item.put("action", rs.getString("action"));
            item.put("beforeSnapshot", rs.getString("before_snapshot"));
            item.put("afterSnapshot", rs.getString("after_snapshot"));
            item.put("reason", rs.getString("reason"));
            item.put("approvedAt", rs.getTimestamp("approved_at"));
            return item;
        }, answerId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /** 返回事件内下一个候选答案版本；版本只在事件范围内递增。 */
    public int nextAnswerVersion(long eventId) {
        Integer current = jdbcTemplate.queryForObject(
                "SELECT COALESCE(MAX(answer_version),0) FROM answer_candidate WHERE event_id=?",
                Integer.class, eventId);
        return (current == null ? 0 : current) + 1;
    }

    public int insertEvidence(long answerId, String evidenceKey, String sourceType,
                              String documentId, String documentVersion, String sectionName,
                              String quoteText, String contentHash) {
        return jdbcTemplate.update("""
                INSERT INTO answer_evidence(answer_id,evidence_key,source_type,document_id,document_version,
                                            section_name,quote_text,content_hash)
                VALUES(?,?,?,?,?,?,?,?)
                """, answerId, evidenceKey, sourceType, documentId, documentVersion,
                sectionName, quoteText, contentHash);
    }

    public int insertValidation(long answerId, String schemaResult, String evidenceResult,
                                String ruleResult, String completenessResult, String orderResult,
                                String permissionResult, String finalResult, String failureReason,
                                String validatorVersion) {
        return insertValidation(answerId, schemaResult, evidenceResult, ruleResult, completenessResult,
                orderResult, permissionResult, "PENDING", finalResult, failureReason, validatorVersion);
    }

    public int insertValidation(long answerId, String schemaResult, String evidenceResult,
                                String ruleResult, String completenessResult, String orderResult,
                                String permissionResult, String freshnessResult, String finalResult,
                                String failureReason, String validatorVersion) {
        return jdbcTemplate.update("""
                INSERT INTO validation_result(answer_id,schema_result,evidence_result,rule_result,
                                              completeness_result,order_result,permission_result,freshness_result,
                                              final_result,failure_reason,validator_version)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """, answerId, schemaResult, evidenceResult, ruleResult, completenessResult,
                orderResult, permissionResult, freshnessResult, finalResult, failureReason, validatorVersion);
    }

    public List<Map<String, Object>> findEvidence(long answerId) {
        return jdbcTemplate.query("""
                SELECT id,evidence_key,source_type,document_id,document_version,section_name,
                       quote_text,content_hash,created_at
                FROM answer_evidence WHERE answer_id=? ORDER BY id ASC
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("evidenceKey", rs.getString("evidence_key"));
            item.put("sourceType", rs.getString("source_type"));
            item.put("documentId", rs.getString("document_id"));
            item.put("documentVersion", rs.getString("document_version"));
            item.put("section", rs.getString("section_name"));
            item.put("quote", rs.getString("quote_text"));
            item.put("contentHash", rs.getString("content_hash"));
            item.put("createdAt", rs.getTimestamp("created_at"));
            return item;
        }, answerId);
    }

    public Map<String, Object> findLatestValidation(long answerId) {
        List<Map<String, Object>> rows = jdbcTemplate.query("""
                SELECT id,answer_id,schema_result,evidence_result,rule_result,completeness_result,
                       order_result,permission_result,freshness_result,final_result,failure_reason,
                       validator_version,created_at
                FROM validation_result WHERE answer_id=? ORDER BY id DESC LIMIT 1
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("answerId", rs.getLong("answer_id"));
            item.put("schemaResult", rs.getString("schema_result"));
            item.put("evidenceResult", rs.getString("evidence_result"));
            item.put("ruleResult", rs.getString("rule_result"));
            item.put("completenessResult", rs.getString("completeness_result"));
            item.put("orderResult", rs.getString("order_result"));
            item.put("permissionResult", rs.getString("permission_result"));
            item.put("freshnessResult", rs.getString("freshness_result"));
            item.put("finalResult", rs.getString("final_result"));
            item.put("failureReason", rs.getString("failure_reason"));
            item.put("validatorVersion", rs.getString("validator_version"));
            item.put("createdAt", rs.getTimestamp("created_at"));
            return item;
        }, answerId);
        return rows.isEmpty() ? null : rows.get(0);
    }

    /** 将人工修改前答案的证据绑定复制到新版本，保证每个可执行版本独立可追溯。 */
    public int copyEvidence(long sourceAnswerId, long targetAnswerId) {
        return jdbcTemplate.update("""
                INSERT INTO answer_evidence(answer_id,evidence_key,source_type,document_id,document_version,
                                            section_name,quote_text,content_hash)
                SELECT ?,evidence_key,source_type,document_id,document_version,section_name,quote_text,content_hash
                FROM answer_evidence WHERE answer_id=?
                """, targetAnswerId, sourceAnswerId);
    }

    public int updateAnswerStatus(long answerId, String status) {
        return jdbcTemplate.update("UPDATE answer_candidate SET status=? WHERE id=?", status, answerId);
    }

    public int insertApproval(long answerId, long operatorId, String operatorRole, String action,
                              String beforeSnapshot, String afterSnapshot, String reason) {
        return jdbcTemplate.update("""
                INSERT INTO approval_record(answer_id,operator_id,operator_role,action,before_snapshot,
                                            after_snapshot,reason)
                VALUES(?,?,?,?,?,?,?)
                """, answerId, operatorId, operatorRole, action, beforeSnapshot, afterSnapshot, reason);
    }

    /** 追加一条审计记录；调用方必须先完成脱敏并计算 currentHash。 */
    public int appendAudit(long eventId, Long workflowInstanceId, Long answerId, String operationType,
                           Long operatorId, String requestSnapshot, String responseSnapshot,
                           String previousHash, String currentHash) {
        return jdbcTemplate.update("""
                INSERT INTO audit_event(event_id,workflow_instance_id,answer_id,operation_type,operator_id,
                                        request_snapshot,response_snapshot,previous_hash,current_hash)
                VALUES(?,?,?,?,?,?,?,?,?)
                """, eventId, workflowInstanceId, answerId, operationType, operatorId,
                requestSnapshot, responseSnapshot, previousHash, currentHash);
    }

    public String findLatestAuditHash(long eventId) {
        List<String> hashes = jdbcTemplate.query("""
                SELECT current_hash FROM audit_event WHERE event_id=? ORDER BY id DESC LIMIT 1
                """, (rs, row) -> rs.getString(1), eventId);
        return hashes.isEmpty() ? null : hashes.get(0);
    }

    public List<Map<String, Object>> findAuditTrail(long eventId) {
        return jdbcTemplate.query("""
                SELECT id,event_id,workflow_instance_id,answer_id,operation_type,operator_id,
                       request_snapshot,response_snapshot,previous_hash,current_hash,created_at
                FROM audit_event WHERE event_id=? ORDER BY id ASC
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventId", rs.getLong("event_id"));
            item.put("workflowInstanceId", rs.getObject("workflow_instance_id", Long.class));
            item.put("answerId", rs.getObject("answer_id", Long.class));
            item.put("operationType", rs.getString("operation_type"));
            item.put("operatorId", rs.getObject("operator_id", Long.class));
            item.put("requestSnapshot", rs.getString("request_snapshot"));
            item.put("responseSnapshot", rs.getString("response_snapshot"));
            item.put("previousHash", rs.getString("previous_hash"));
            item.put("currentHash", rs.getString("current_hash"));
            item.put("createdAt", rs.getTimestamp("created_at"));
            return item;
        }, eventId);
    }

    /** 按事件返回全部答案版本及各自最新的校验、审批与证据快照。 */
    public List<Map<String, Object>> findEventAnswerHistory(long eventId) {
        List<Map<String, Object>> answers = jdbcTemplate.query("""
                SELECT id,event_id,workflow_instance_id,answer_version,source,status,schema_version,
                       answer_json,model_name,model_version,knowledge_version,created_by,created_at
                FROM answer_candidate WHERE event_id=? ORDER BY answer_version ASC,id ASC
                """, (rs, row) -> {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", rs.getLong("id"));
            item.put("eventId", rs.getLong("event_id"));
            item.put("workflowInstanceId", rs.getObject("workflow_instance_id", Long.class));
            item.put("answerVersion", rs.getInt("answer_version"));
            item.put("source", rs.getString("source"));
            item.put("status", rs.getString("status"));
            item.put("schemaVersion", rs.getString("schema_version"));
            item.put("answerJson", rs.getString("answer_json"));
            item.put("modelName", rs.getString("model_name"));
            item.put("modelVersion", rs.getString("model_version"));
            item.put("knowledgeVersion", rs.getString("knowledge_version"));
            item.put("createdBy", rs.getObject("created_by", Long.class));
            item.put("createdAt", rs.getTimestamp("created_at"));
            return item;
        }, eventId);
        for (Map<String, Object> answer : answers) {
            long answerId = ((Number) answer.get("id")).longValue();
            answer.put("evidence", findEvidence(answerId));
            answer.put("validation", findLatestValidation(answerId));
            answer.put("approval", findLatestApproval(answerId));
        }
        return answers;
    }
}
