package com.metro.emergency.dto;

/** 管理员为本站工作人员重置密码时提交的新密码。 */
public record ResetPasswordRequest(String newPassword) {
}
