package com.metro.emergency.common;

/**
 * 前后端统一响应结构。
 *
 * @param code    业务状态码，200 表示成功
 * @param message 提示信息
 * @param data    响应数据
 */
public record ApiResponse<T>(int code, String message, T data) {

    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(200, "操作成功", data);
    }

    public static <T> ApiResponse<T> failure(int code, String message) {
        return new ApiResponse<>(code, message, null);
    }
}
