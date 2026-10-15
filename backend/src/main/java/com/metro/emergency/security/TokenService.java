package com.metro.emergency.security;

import com.metro.emergency.exception.AuthenticationException;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 联调阶段的内存令牌服务。服务重启后令牌自动失效，后续可无缝替换为 JWT。
 */
@Service
public class TokenService {

    private final Map<String, LoginIdentity> tokenUsers = new ConcurrentHashMap<>();

    public String issue(long userId, String username) {
        String token = UUID.randomUUID().toString();
        tokenUsers.put(token, new LoginIdentity(userId, username));
        return token;
    }

    public String requireUsername(String authorization) {
        return requireIdentity(authorization).username();
    }

    public LoginIdentity requireIdentity(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new AuthenticationException("登录状态无效，请重新登录");
        }
        LoginIdentity identity = tokenUsers.get(authorization.substring(7));
        if (identity == null) {
            throw new AuthenticationException("登录状态已过期，请重新登录");
        }
        return identity;
    }

    public LoginIdentity requireToken(String token) {
        LoginIdentity identity = token == null ? null : tokenUsers.get(token);
        if (identity == null) {
            throw new AuthenticationException("登录状态已过期，请重新登录");
        }
        return identity;
    }

    public void revoke(String authorization) {
        if (authorization != null && authorization.startsWith("Bearer ")) {
            tokenUsers.remove(authorization.substring(7));
        }
    }

    public record LoginIdentity(long userId, String username) {
    }
}
