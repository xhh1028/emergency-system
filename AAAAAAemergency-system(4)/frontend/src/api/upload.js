// 文件上传接口封装
import request from '@/utils/request'

/**
 * 上传文件
 * POST /api/upload
 * @param {FormData} formData 表单数据，包含 file 字段
 */
export function uploadFile(formData) {
  return request({
    url: '/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}