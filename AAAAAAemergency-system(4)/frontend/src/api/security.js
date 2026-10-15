// 资源与安保模块接口封装
import request from '@/utils/request'

/**
 * 查询应急资源列表
 * GET /api/resources
 * @param {Object} params 入参 { category }
 */
export function getResources(params) {
  return request({
    url: '/resources',
    method: 'get',
    params
  })
}

/**
 * 资源调拨
 * POST /api/resources/:id/transfer
 * @param {Number|String} id 资源ID
 * @param {Object} data 入参 { toStation, qty }
 */
export function transferResource(id, data) {
  return request({
    url: `/resources/${id}/transfer`,
    method: 'post',
    data
  })
}

/**
 * 资源补充
 * POST /api/resources/:id/replenish
 * @param {Number|String} id 资源ID
 * @param {Object} data 入参 { qty }
 */
export function replenishResource(id, data) {
  return request({
    url: `/resources/${id}/replenish`,
    method: 'post',
    data
  })
}

/**
 * 资源盘点
 * POST /api/resources/:id/inventory
 * @param {Number|String} id 资源ID
 * @param {Object} data 入参 { actualQty }
 */
export function inventoryResource(id, data) {
  return request({
    url: `/resources/${id}/inventory`,
    method: 'post',
    data
  })
}

/**
 * 查询安保人员状态列表
 * GET /api/security/personnel
 * @param {Object} params 入参 { station, status }
 */
export function getSecurityPersonnel(params) {
  return request({
    url: '/security/personnel',
    method: 'get',
    params
  })
}