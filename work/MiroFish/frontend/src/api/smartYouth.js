import service from './index'

export const searchSmartYouthRecords = (capabilityId, payload = {}) => {
  return service.post(`/api/smart-youth/capabilities/${capabilityId}/searchRecords`, payload)
}

export const getSmartYouthMeta = () => {
  return service.get('/api/smart-youth/meta')
}

