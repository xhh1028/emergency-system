package com.metro.emergency.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 为既有 RDS 表补充本项目后续阶段所需的非破坏性字段。
 * 这里只增加列并回填兼容数据，不会删除、重命名任何用户表或字段。
 */
@Component
public class SchemaCompatibilityMigration {
    private static final Logger log = LoggerFactory.getLogger(SchemaCompatibilityMigration.class);
    private final JdbcTemplate jdbcTemplate;

    public SchemaCompatibilityMigration(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void migrate() {
        try {
            addColumnIfMissing("event", "event_title", "VARCHAR(200) NULL COMMENT '事件标题'");
            addColumnIfMissing("event", "faulty_device", "VARCHAR(200) NULL COMMENT '故障设备'");
            addColumnIfMissing("event", "ai_reason", "VARCHAR(1000) NULL COMMENT 'AI研判依据'");
            addColumnIfMissing("event", "ai_source", "VARCHAR(32) NULL COMMENT 'AI研判来源'");
            addColumnIfMissing("event", "ai_plan", "TEXT NULL COMMENT 'AI生成处置预案'");
            addColumnIfMissing("event", "dispatch_confirm", "TINYINT(1) NOT NULL DEFAULT 0 COMMENT '调度已确认'");
            addColumnIfMissing("event", "dispatch_confirm_time", "DATETIME NULL COMMENT '调度确认时间'");
            addColumnIfMissing("event", "close_time", "DATETIME NULL COMMENT '事件关闭时间'");
            addColumnIfMissing("event", "is_emergency", "TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否紧急险情'");
            addColumnIfMissing("event", "reject_reason", "VARCHAR(500) NULL COMMENT '驳回理由'");
            addColumnIfMissing("event", "reject_time", "DATETIME NULL COMMENT '驳回时间'");
            addColumnIfMissing("dispatch_command", "answer_id", "BIGINT NULL COMMENT '批准答案版本ID'");
            addColumnIfMissing("dispatch_command", "answer_version", "INT NULL COMMENT '事件内答案版本'");
            addColumnIfMissing("dispatch_command", "validation_id", "BIGINT NULL COMMENT '通过校验结果ID'");
            addColumnIfMissing("dispatch_command", "evidence_snapshot", "LONGTEXT NULL COMMENT '下发时证据快照'");
            // 事件撤回（逻辑删除）：0=正常，1=已撤回；禁止物理删除，仅置标记并写 event_log
            addColumnIfMissing("event", "is_withdraw", "TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已撤回：0正常，1已撤回'");
            addColumnIfMissing("task", "evaluation", "VARCHAR(500) NULL COMMENT '调度评价'");
            // 事件流转日志：留存紧急标记、跳过驳回记录、AI 研判结果、人工最终等级等。
            // 复用既有 event_log 表结构，仅在表不存在时创建。
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS event_log (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        event_id BIGINT NOT NULL COMMENT '事件ID',
                        operate_user_id BIGINT NOT NULL COMMENT '操作人',
                        operate_type VARCHAR(30) NOT NULL COMMENT '操作类型',
                        ai_suggest_level VARCHAR(20) NULL COMMENT 'AI研判等级',
                        final_event_level VARCHAR(20) NULL COMMENT '人工最终等级',
                        operate_desc VARCHAR(800) NULL COMMENT '操作描述',
                        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件流转日志'
                    """);

            // 双轨答案工作流的非破坏性持久化模型。答案、证据、校验、审批和审计均独立版本化，
            // 不改动既有 event、task、pre_plan 表，也不把 AI 候选结果直接写成执行指令。
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_instance (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        event_id BIGINT NOT NULL COMMENT '关联事件ID',
                        workflow_type VARCHAR(20) NOT NULL COMMENT 'RIGID 或 AI_ASSIST',
                        current_state VARCHAR(40) NOT NULL COMMENT '工作流当前状态',
                        version INT NOT NULL DEFAULT 1 COMMENT '工作流版本',
                        correlation_id VARCHAR(64) NOT NULL COMMENT '跨服务追踪标识',
                        created_by BIGINT NULL COMMENT '创建人ID',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        KEY idx_workflow_event (event_id),
                        KEY idx_workflow_correlation (correlation_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='双轨工作流实例'
                    """);
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS answer_candidate (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        event_id BIGINT NOT NULL COMMENT '关联事件ID',
                        workflow_instance_id BIGINT NULL COMMENT '关联工作流实例',
                        answer_version INT NOT NULL COMMENT '事件内答案版本',
                        source VARCHAR(20) NOT NULL COMMENT 'RULE、LLM 或 HUMAN',
                        status VARCHAR(20) NOT NULL COMMENT 'GENERATED、VALIDATED、ACCEPTED、MODIFIED、REJECTED',
                        schema_version VARCHAR(32) NOT NULL,
                        answer_json LONGTEXT NOT NULL COMMENT '结构化答案快照',
                        model_name VARCHAR(128) NULL,
                        model_version VARCHAR(128) NULL,
                        prompt_hash CHAR(64) NULL,
                        knowledge_version VARCHAR(128) NULL,
                        created_by BIGINT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE KEY uk_answer_event_version (event_id, answer_version),
                        KEY idx_answer_workflow (workflow_instance_id),
                        KEY idx_answer_status (event_id, status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='AI及规则候选答案版本'
                    """);
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS answer_evidence (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        answer_id BIGINT NOT NULL COMMENT '候选答案ID',
                        evidence_key VARCHAR(64) NOT NULL,
                        source_type VARCHAR(20) NOT NULL COMMENT 'RAG、PRE_PLAN 或 RULE',
                        document_id VARCHAR(255) NOT NULL,
                        document_version VARCHAR(128) NULL,
                        section_name VARCHAR(255) NULL,
                        quote_text TEXT NULL,
                        content_hash CHAR(64) NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_evidence_answer (answer_id),
                        UNIQUE KEY uk_evidence_answer_key (answer_id, evidence_key)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='答案依据证据片段'
                    """);
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS validation_result (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        answer_id BIGINT NOT NULL COMMENT '候选答案ID',
                        schema_result VARCHAR(16) NOT NULL,
                        evidence_result VARCHAR(16) NOT NULL,
                        rule_result VARCHAR(16) NOT NULL,
                        completeness_result VARCHAR(16) NOT NULL,
                        order_result VARCHAR(16) NOT NULL,
                        permission_result VARCHAR(16) NOT NULL,
                        freshness_result VARCHAR(16) NOT NULL DEFAULT 'PENDING',
                        final_result VARCHAR(16) NOT NULL COMMENT 'PASS 或 FAIL',
                        failure_reason TEXT NULL,
                        validator_version VARCHAR(64) NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_validation_answer (answer_id),
                        KEY idx_validation_final (final_result)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='答案独立校验结果'
                    """);
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS approval_record (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        answer_id BIGINT NOT NULL COMMENT '候选答案ID',
                        operator_id BIGINT NOT NULL COMMENT '审批人ID',
                        operator_role VARCHAR(64) NOT NULL,
                        action VARCHAR(16) NOT NULL COMMENT 'ACCEPTED、MODIFIED 或 REJECTED',
                        before_snapshot LONGTEXT NULL,
                        after_snapshot LONGTEXT NULL,
                        reason VARCHAR(1000) NULL,
                        approved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_approval_answer (answer_id),
                        KEY idx_approval_operator (operator_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='答案人工审批记录'
                    """);
            jdbcTemplate.execute("""
                    CREATE TABLE IF NOT EXISTS audit_event (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        event_id BIGINT NOT NULL COMMENT '关联事件ID',
                        workflow_instance_id BIGINT NULL,
                        answer_id BIGINT NULL,
                        operation_type VARCHAR(40) NOT NULL,
                        operator_id BIGINT NULL,
                        request_snapshot LONGTEXT NULL,
                        response_snapshot LONGTEXT NULL,
                        previous_hash CHAR(64) NULL,
                        current_hash CHAR(64) NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        KEY idx_audit_event_time (event_id, id),
                        KEY idx_audit_workflow (workflow_instance_id),
                        KEY idx_audit_answer (answer_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='双轨工作流追加式审计链'
                    """);

            addColumnIfMissing("validation_result", "freshness_result", "VARCHAR(16) NOT NULL DEFAULT 'PENDING' COMMENT '知识版本新鲜度校验结果'");
            addCommandAnswerUniqueIndex();

            jdbcTemplate.update("""
                    UPDATE event SET event_title=CONCAT(event_type,'-',event_no)
                    WHERE event_title IS NULL OR TRIM(event_title)=''
                    """);
            jdbcTemplate.update("""
                    UPDATE event SET dispatch_confirm=1,dispatch_confirm_time=COALESCE(dispatch_confirm_time,create_time),
                                     final_event_level='UNCONFIRMED'
                    WHERE final_event_level='DISPATCH_CONFIRMED'
                    """);
            jdbcTemplate.update("""
                    UPDATE event SET close_time=COALESCE(close_time,create_time)
                    WHERE event_status='FINISHED' AND close_time IS NULL
                    """);
        } catch (Exception exception) {
            // 测试切片使用模拟数据源；生产环境若无 ALTER 权限，也应输出明确日志而不是阻止登录服务启动。
            log.warn("数据库兼容字段迁移未完成，请检查 RDS 账号 ALTER 权限：{}", exception.getMessage());
        }
    }

    private void addColumnIfMissing(String table, String column, String definition) {
        List<Integer> matches = jdbcTemplate.query("""
                SELECT 1 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=? AND COLUMN_NAME=? LIMIT 1
                """, (rs, row) -> 1, table, column);
        if (matches.isEmpty()) {
            jdbcTemplate.execute("ALTER TABLE `" + table + "` ADD COLUMN `" + column + "` " + definition);
            log.info("已为 {} 表增加字段 {}", table, column);
        }
    }

    private void addCommandAnswerUniqueIndex() {
        List<Integer> matches = jdbcTemplate.query("""
                SELECT 1 FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='dispatch_command'
                  AND INDEX_NAME='uk_command_answer_version' LIMIT 1
                """, (rs, row) -> 1);
        if (matches.isEmpty()) {
            jdbcTemplate.execute("CREATE UNIQUE INDEX uk_command_answer_version ON dispatch_command(event_id,answer_id,answer_version)");
        }
    }
}
