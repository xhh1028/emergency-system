package com.metro.emergency.dto;

/** 车站管理员新增或编辑本站工作人员时提交的数据。 */
public record PersonnelSaveRequest(
        String realName,
        String phone,
        String role,
        Integer postId,
        String status,
        String initialPassword
) {
}
