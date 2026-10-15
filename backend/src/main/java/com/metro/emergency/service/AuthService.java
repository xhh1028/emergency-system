package com.metro.emergency.service;

import com.metro.emergency.dto.LoginRequest;
import com.metro.emergency.dto.LoginResponse;
import com.metro.emergency.dto.RoleInfo;
import com.metro.emergency.dto.UserInfo;
import com.metro.emergency.exception.AuthenticationException;
import com.metro.emergency.repository.UserAccount;
import com.metro.emergency.repository.UserRepository;
import com.metro.emergency.security.PasswordHasher;
import com.metro.emergency.security.TokenService;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 登录业务服务。
 * 从 RDS MySQL 查询用户，并校验 PBKDF2 密码哈希。
 */
@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordHasher passwordHasher;
    private final TokenService tokenService;

    private static final List<RoleInfo> ROLES = List.of(
            new RoleInfo(1, "dispatch_center", "调度指挥", "/dispatch/overview"),
            new RoleInfo(2, "station", "车站管理", "/station/event-todo"),
            new RoleInfo(3, "field", "一线执行", "/field/tasks"),
            new RoleInfo(4, "support", "后勤安保", "/support/todos")
    );

    public AuthService(UserRepository userRepository, PasswordHasher passwordHasher, TokenService tokenService) {
        this.userRepository = userRepository;
        this.passwordHasher = passwordHasher;
        this.tokenService = tokenService;
    }

    public List<RoleInfo> getRoles() {
        return ROLES;
    }

    public LoginResponse login(LoginRequest request) {
        UserAccount user = userRepository.findByUsername(request.username())
                .filter(UserAccount::enabled)
                .orElseThrow(() -> new AuthenticationException("用户名或密码错误"));
        if (!passwordHasher.matches(request.password(), user.passwordHash())) {
            throw new AuthenticationException("用户名或密码错误");
        }

        UserInfo userInfo = new UserInfo(
                user.id(),
                user.username(),
                user.nickname(),
                user.role(),
                user.roleLabel(),
                user.subRole(),
                user.subRoleLabel(),
                "https://api.dicebear.com/7.x/bottts/svg?seed=" + user.username()
        );

        return new LoginResponse(tokenService.issue(user.id(), user.username()), userInfo);
    }

    public void changePassword(String authorization, String oldPassword, String newPassword) {
        String username = tokenService.requireUsername(authorization);
        UserAccount user = userRepository.findByUsername(username)
                .orElseThrow(() -> new AuthenticationException("当前账号不存在"));
        if (!passwordHasher.matches(oldPassword, user.passwordHash())) {
            throw new AuthenticationException("原密码错误");
        }
        if (oldPassword.equals(newPassword)) {
            throw new AuthenticationException("新密码不能与原密码相同");
        }
        if (userRepository.updatePasswordHash(username, passwordHasher.hash(newPassword)) != 1) {
            throw new IllegalStateException("密码修改失败");
        }
        tokenService.revoke(authorization);
    }

    public void logout(String authorization) {
        tokenService.revoke(authorization);
    }

    public Map<String, Object> profile(String authorization) {
        long userId = tokenService.requireIdentity(authorization).userId();
        Map<String, Object> profile = userRepository.findProfile(userId);
        if (profile == null) throw new AuthenticationException("当前账号不存在");
        return profile;
    }
}
