package com.metro.emergency.config;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.contains;

class SchemaCompatibilityMigrationTest {
    @Test
    void createsValidationTableBeforeAlteringAndAddsCommandDuplicateProtection() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);

        new SchemaCompatibilityMigration(jdbc).migrate();

        var order = inOrder(jdbc);
        order.verify(jdbc).execute(contains("CREATE TABLE IF NOT EXISTS validation_result"));
        order.verify(jdbc).execute(contains("ALTER TABLE `validation_result` ADD COLUMN `freshness_result`"));
        order.verify(jdbc).execute(contains("CREATE UNIQUE INDEX uk_command_answer_version"));
    }
}
