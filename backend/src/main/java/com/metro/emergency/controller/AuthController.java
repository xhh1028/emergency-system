package com.metro.emergency.controller;

import com.metro.emergency.common.ApiResponse;
import com.metro.emergency.dto.LoginRequest;
import com.metro.emergency.dto.LoginResponse;
import com.metro.emergency.dto.RoleInfo;
import com.metro.emergency.dto.ChangePasswordRequest;
import com.metro.emergency.service.AuthService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 用户认证接口。
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @GetMapping("/roles")
    public ApiResponse<List<RoleInfo>> getRoles() {
        return ApiResponse.success(authService.getRoles());
    }

    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return ApiResponse.success(authService.login(request));
    }

    @PostMapping("/logout")
    public ApiResponse<Void> logout(@RequestHeader(value = "Authorization", required = false) String authorization) {
        authService.logout(authorization);
        return ApiResponse.success(null);
    }

    @PostMapping("/change-password")
    public ApiResponse<Void> changePassword(
            @RequestHeader("Authorization") String authorization,
            @Valid @RequestBody ChangePasswordRequest request) {
        authService.changePassword(authorization, request.oldPassword(), request.newPassword());
        return ApiResponse.success(null);
    }

    @GetMapping("/profile")
    public ApiResponse<Map<String, Object>> profile(
            @RequestHeader("Authorization") String authorization) {
        return ApiResponse.success(authService.profile(authorization));
    }
}
