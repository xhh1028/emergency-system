package com.metro.emergency.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * 事件等级智能研判服务。
 * 配置 OpenAI 兼容接口后优先调用大模型；未配置、超时或响应异常时自动使用可解释规则，
 * 确保事件上报不会因为外部 AI 服务故障而中断。
 */
@Service
public class AiAssessmentService {

    private final ObjectMapper objectMapper;
    private final String endpoint;
    private final String apiKey;
    private final String model;
    private final RestClient restClient;

    public AiAssessmentService(
            ObjectMapper objectMapper,
            @Value("${app.ai.endpoint:}") String endpoint,
            @Value("${app.ai.api-key:}") String apiKey,
            @Value("${app.ai.model:}") String model) {
        this.objectMapper = objectMapper;
        this.endpoint = endpoint == null ? "" : endpoint.trim();
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.model = model == null ? "" : model.trim();
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(3));
        factory.setReadTimeout(Duration.ofSeconds(8));
        this.restClient = RestClient.builder().requestFactory(factory).build();
    }

    public Assessment assess(String eventType, String description, String reporterLevel) {
        if (!endpoint.isBlank() && !apiKey.isBlank() && !model.isBlank()) {
            try {
                Assessment result = assessWithModel(eventType, description, reporterLevel);
                if (result != null) return result;
            } catch (Exception ignored) {
                // 外部模型不可用时必须降级，不能阻断险情上报主流程。
            }
        }
        return assessWithRules(eventType, description, reporterLevel);
    }

    private Assessment assessWithModel(String eventType, String description, String reporterLevel) throws Exception {
        String prompt = """
                你是城市轨道交通应急事件研判助手。请综合事件类型、一线上报等级和描述进行安全研判，
                并生成可执行的处置预案。只返回 JSON，不要使用 Markdown，格式为：
                {"level":"GENERAL|SERIOUS|EXTREMELY_SERIOUS","reason":"研判依据","plan":"分步骤处置预案"}
                事件类型：%s
                一线上报等级：%s
                事件描述：%s
                """.formatted(eventType, reporterLevel, description);
        Map<String, Object> body = Map.of(
                "model", model,
                "temperature", 0,
                "messages", List.of(
                        Map.of("role", "system", "content", "你负责轨道交通应急事件等级研判。"),
                        Map.of("role", "user", "content", prompt)));
        String response = restClient.post()
                .uri(endpoint)
                .header("Authorization", "Bearer " + apiKey)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .body(String.class);
        JsonNode root = objectMapper.readTree(response);
        String rawContent = root.path("choices").path(0).path("message").path("content").asText("").trim();
        String content = rawContent.toUpperCase(Locale.ROOT);
        try {
            String json = rawContent.replaceFirst("(?s)^```(?:json)?\\s*", "").replaceFirst("(?s)\\s*```$", "");
            JsonNode result = objectMapper.readTree(json);
            String level = result.path("level").asText("").toUpperCase(Locale.ROOT);
            if (List.of("GENERAL", "SERIOUS", "EXTREMELY_SERIOUS").contains(level)) {
                String reason = result.path("reason").asText("大模型综合事件信息完成研判");
                String plan = result.path("plan").asText("");
                if (!plan.isBlank()) return new Assessment(level, reason, "LLM", plan);
            }
        } catch (Exception ignored) {
            // 兼容只返回等级的模型，随后采用默认处置步骤。
        }
        for (String level : List.of("EXTREMELY_SERIOUS", "SERIOUS", "GENERAL")) {
            if (content.contains(level)) {
                return new Assessment(level, "大模型综合事件类型、上报等级和描述完成研判", "LLM",
                        defaultPlan(eventType, level));
            }
        }
        return null;
    }

    private Assessment assessWithRules(String eventType, String description, String reporterLevel) {
        String text = (description == null ? "" : description).toLowerCase(Locale.ROOT);
        int score = switch (eventType == null ? "" : eventType) {
            case "FIRE", "TRACK_OPERATION" -> 3;
            case "CROWD_SECURITY", "DISASTER_ENVIRONMENT" -> 2;
            case "PASSENGER", "DEVICE_FAILURE" -> 1;
            default -> 0;
        };
        score += switch (reporterLevel == null ? "" : reporterLevel) {
            case "EXTREMELY_SERIOUS" -> 4;
            case "SERIOUS" -> 2;
            default -> 0;
        };
        String[] criticalWords = {"死亡", "爆炸", "脱轨", "劫持", "大面积停运", "多人被困", "浓烟", "失火"};
        String[] seriousWords = {"受伤", "中断", "拥堵", "异物", "故障扩大", "无法通行", "紧急停车", "疏散"};
        for (String word : criticalWords) if (text.contains(word)) score += 4;
        for (String word : seriousWords) if (text.contains(word)) score += 2;

        String level = score >= 7 ? "EXTREMELY_SERIOUS" : score >= 3 ? "SERIOUS" : "GENERAL";
        return new Assessment(level, "综合事件类型、上报等级及描述风险关键词计算；规则评分=" + score,
                "RULE_FALLBACK", defaultPlan(eventType, level));
    }

    private String defaultPlan(String eventType, String level) {
        String action = switch (eventType == null ? "" : eventType) {
            case "FIRE" -> "切断相关区域非必要电源，启用消防设施并组织乘客向安全出口疏散";
            case "DEVICE_FAILURE" -> "隔离故障设备，设置警戒标识并安排专业人员抢修";
            case "PASSENGER" -> "疏散围观人员，开展现场救助并联系医疗力量";
            case "TRACK_OPERATION" -> "立即采取行车防护措施，封锁相关区段并报告行车调度";
            case "CROWD_SECURITY" -> "实施客流管控和分流，增派安保力量维护现场秩序";
            case "DISASTER_ENVIRONMENT" -> "划定危险区域，监测环境风险并组织人员转移";
            default -> "隔离现场风险，组织人员疏散并通知相关专业力量到场";
        };
        String escalation = "EXTREMELY_SERIOUS".equals(level)
                ? "立即上报调度指挥中心并请求外部应急力量支援"
                : "持续监测风险变化，必要时升级响应并上报调度";
        return "1. 立即确认现场位置、影响范围及人员情况；\n2. " + action
                + "；\n3. " + escalation + "；\n4. 每个处置节点反馈进度，风险解除后清点人员并形成闭环记录。";
    }

    public record Assessment(String level, String reason, String source, String plan) {
    }
}
