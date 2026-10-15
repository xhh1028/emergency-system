package com.metro.emergency.exception;

/**
 * 用户名或密码校验失败时抛出的业务异常。
 */
public class AuthenticationException extends RuntimeException {

    public AuthenticationException(String message) {
        super(message);
    }
}
