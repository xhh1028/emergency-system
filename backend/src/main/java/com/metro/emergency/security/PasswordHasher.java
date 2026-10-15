package com.metro.emergency.security;

import org.springframework.stereotype.Component;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.security.NoSuchAlgorithmException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.spec.InvalidKeySpecException;
import java.util.Arrays;
import java.util.Base64;

/**
 * 基于 PBKDF2-HMAC-SHA256 的密码哈希工具，不保存明文密码。
 */
@Component
public class PasswordHasher {

    private static final int ITERATIONS = 120_000;
    private static final int KEY_LENGTH = 192;
    private static final int SALT_LENGTH = 12;
    private static final String ALGORITHM = "PBKDF2WithHmacSHA256";
    private final SecureRandom secureRandom = new SecureRandom();

    public String hash(String password) {
        byte[] salt = new byte[SALT_LENGTH];
        secureRandom.nextBytes(salt);
        byte[] derivedKey = derive(password, salt, ITERATIONS);
        // p2$ + 16位盐 + 32位派生密钥，共51字符，可安全存入 sys_user.password varchar(64)。
        return "p2$" + Base64.getEncoder().withoutPadding().encodeToString(salt)
                + "$" + Base64.getEncoder().withoutPadding().encodeToString(derivedKey);
    }

    public boolean matches(String password, String encodedHash) {
        try {
            if (!encodedHash.startsWith("p2$")) {
                // 兼容数据库中的历史密码；用户修改密码后自动换成 PBKDF2 格式。
                return MessageDigest.isEqual(
                        password.getBytes(java.nio.charset.StandardCharsets.UTF_8),
                        encodedHash.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
            String[] parts = encodedHash.split("\\$", 3);
            byte[] salt = Base64.getDecoder().decode(parts[1]);
            byte[] expected = Base64.getDecoder().decode(parts[2]);
            return Arrays.equals(expected, derive(password, salt, ITERATIONS));
        } catch (IllegalArgumentException exception) {
            return false;
        }
    }

    private byte[] derive(String password, byte[] salt, int iterations) {
        PBEKeySpec specification = new PBEKeySpec(password.toCharArray(), salt, iterations, KEY_LENGTH);
        try {
            return SecretKeyFactory.getInstance(ALGORITHM).generateSecret(specification).getEncoded();
        } catch (NoSuchAlgorithmException | InvalidKeySpecException exception) {
            throw new IllegalStateException("当前 Java 环境不支持密码哈希算法", exception);
        } finally {
            specification.clearPassword();
        }
    }
}
