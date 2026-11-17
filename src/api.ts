import type { FloorplanData } from './types'

export async function fetchFloorplan(projectId = 'apartment'): Promise<FloorplanData> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`户型数据加载失败（${response.status}）：${detail}`)
  }
  return response.json() as Promise<FloorplanData>
}
