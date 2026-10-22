package com.metro.emergency.dto;

/** 调度人员向事件所属车站下发正式处置指令。 */
public record DispatchCommandRequest(Long answerId, Integer answerVersion, String finalLevel, String content) {
    public DispatchCommandRequest(String finalLevel, String content) {
        this(null, null, finalLevel, content);
    }
}
