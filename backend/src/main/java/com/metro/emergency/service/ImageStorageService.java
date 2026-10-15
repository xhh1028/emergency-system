package com.metro.emergency.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** 现场图片校验和本地存储服务，供险情上报与任务反馈共用。 */
@Service
public class ImageStorageService {

    private static final Set<String> IMAGE_TYPES = Set.of("image/jpeg", "image/png", "image/webp");
    private final Path uploadRoot;

    public ImageStorageService(@Value("${app.upload-dir:uploads}") String uploadDir) {
        this.uploadRoot = Path.of(uploadDir).toAbsolutePath().normalize();
    }

    public String saveImages(List<MultipartFile> images) {
        if (images == null || images.isEmpty()) return "";
        if (images.size() > 5) throw new IllegalArgumentException("现场图片最多上传5张");

        try {
            Files.createDirectories(uploadRoot);
            List<String> urls = new ArrayList<>();
            for (MultipartFile image : images) {
                if (image == null || image.isEmpty()) continue;
                if (image.getSize() > 5 * 1024 * 1024) {
                    throw new IllegalArgumentException("单张图片不能超过5MB");
                }
                if (!IMAGE_TYPES.contains(image.getContentType())) {
                    throw new IllegalArgumentException("仅支持 JPG、PNG、WEBP 图片");
                }
                String extension = switch (image.getContentType()) {
                    case "image/png" -> ".png";
                    case "image/webp" -> ".webp";
                    default -> ".jpg";
                };
                String fileName = UUID.randomUUID() + extension;
                Path target = uploadRoot.resolve(fileName).normalize();
                if (!target.startsWith(uploadRoot)) throw new IllegalArgumentException("非法文件路径");
                Files.copy(image.getInputStream(), target, StandardCopyOption.REPLACE_EXISTING);
                urls.add("/uploads/" + fileName);
            }
            return String.join(";", urls);
        } catch (IOException exception) {
            throw new IllegalStateException("现场图片保存失败", exception);
        }
    }
}
