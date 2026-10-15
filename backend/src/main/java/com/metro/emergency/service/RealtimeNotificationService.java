package com.metro.emergency.service;

import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;

/** 进程内 SSE 消息总线；浏览器断线后会自动重连，业务数据仍以数据库接口为准。 */
@Service
public class RealtimeNotificationService {
    private final List<Client> clients = new CopyOnWriteArrayList<>();
    private final AtomicLong sequence = new AtomicLong();

    public SseEmitter subscribe(long userId, String role, Long stationId) {
        SseEmitter emitter = new SseEmitter(0L);
        Client client = new Client(userId, role == null ? "" : role.toUpperCase(), stationId, emitter);
        clients.add(client);
        emitter.onCompletion(() -> clients.remove(client));
        emitter.onTimeout(() -> clients.remove(client));
        emitter.onError(error -> clients.remove(client));
        send(client, message("CONNECTED", "实时连接成功", "已连接应急系统实时消息服务", null));
        return emitter;
    }

    public void publishAll(String type, String title, String content, String path) {
        publish(client -> true, message(type, title, content, path));
    }

    public void publishToRole(String role, String type, String title, String content, String path) {
        publish(client -> client.role().equalsIgnoreCase(role), message(type, title, content, path));
    }

    public void publishToStation(long stationId, String type, String title, String content, String path) {
        publish(client -> client.stationId() != null && client.stationId() == stationId,
                message(type, title, content, path));
    }

    public void publishToUser(long userId, String type, String title, String content, String path) {
        publish(client -> client.userId() == userId, message(type, title, content, path));
    }

    private Map<String, Object> message(String type, String title, String content, String path) {
        return Map.of(
                "id", sequence.incrementAndGet(),
                "type", type,
                "title", title,
                "content", content,
                "path", path == null ? "" : path,
                "time", LocalDateTime.now().toString());
    }

    private void publish(java.util.function.Predicate<Client> filter, Map<String, Object> data) {
        for (Client client : clients) {
            if (filter.test(client)) send(client, data);
        }
    }

    private void send(Client client, Map<String, Object> data) {
        try {
            client.emitter().send(SseEmitter.event().id(String.valueOf(data.get("id"))).name("notification").data(data));
        } catch (IOException | IllegalStateException exception) {
            clients.remove(client);
            client.emitter().complete();
        }
    }

    private record Client(long userId, String role, Long stationId, SseEmitter emitter) {}
}
