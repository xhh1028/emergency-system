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
}
