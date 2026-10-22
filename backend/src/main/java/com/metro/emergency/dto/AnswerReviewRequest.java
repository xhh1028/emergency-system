package com.metro.emergency.dto;

import java.util.Map;

/** 人工复核候选答案；修改时 answer 保存修改后的完整结构化答案。 */
public record AnswerReviewRequest(String action, String reason, Map<String, Object> answer) {
}
