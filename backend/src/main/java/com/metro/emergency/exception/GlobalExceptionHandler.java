package com.metro.emergency.exception;

import com.metro.emergency.common.ApiResponse;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/** 将认证、参数和上传错误转换成前端统一响应格式。 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(AuthenticationException.class)
    public ApiResponse<Void> handleAuthenticationException(AuthenticationException exception) {
        return ApiResponse.failure(401, exception.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ApiResponse<Void> handleValidationException(MethodArgumentNotValidException exception) {
        String message = exception.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(error -> error.getDefaultMessage())
                .orElse("请求参数不正确");
        return ApiResponse.failure(400, message);
    }

    @ExceptionHandler({IllegalArgumentException.class, IllegalStateException.class})
    public ApiResponse<Void> handleIllegalArgumentException(RuntimeException exception) {
        return ApiResponse.failure(400, exception.getMessage());
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ApiResponse<Void> handleMaxUploadSizeException() {
        return ApiResponse.failure(400, "上传文件总大小超出限制");
    }
}
