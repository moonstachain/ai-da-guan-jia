import service from './index'

export const getStrategicTasks = () => {
  return service.get('/api/strategic-tasks')
}
