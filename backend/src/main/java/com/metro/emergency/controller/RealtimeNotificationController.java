package com.metro.emergency.controller;

import com.metro.emergency.repository.UserRepository;
import com.metro.emergency.security.TokenService;
import com.metro.emergency.service.RealtimeNotificationService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/** EventSource 无法设置 Authorization 头，因此实时连接使用登录令牌查询参数。 */
@RestController
@RequestMapping("/api/notifications")
public class RealtimeNotificationController {
    private final TokenService tokenService;
    private final UserRepository userRepository;
    private final RealtimeNotificationService notificationService;

    public RealtimeNotificationController(TokenService tokenService, UserRepository userRepository,
                                          RealtimeNotificationService notificationService) {
        this.tokenService = tokenService;
        this.userRepository = userRepository;
        this.notificationService = notificationService;
    }

    @GetMapping("/stream")
    public SseEmitter stream(@RequestParam("access_token") String token) {
        var identity = tokenService.requireToken(token);
        MapProfile profile = MapProfile.from(userRepository.findRealtimeProfile(identity.userId()));
        return notificationService.subscribe(identity.userId(), profile.role(), profile.stationId());
    }

    private record MapProfile(String role, Long stationId) {
        static MapProfile from(java.util.Map<String, Object> value) {
            if (value == null) return new MapProfile("", null);
            return new MapProfile(String.valueOf(value.getOrDefault("role", "")),
                    (Long) value.get("stationId"));
        }
    }
}
