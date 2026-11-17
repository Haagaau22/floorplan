import type { AnyFloorplanData } from './types'

export async function fetchFloorplan(projectId = 'apartment'): Promise<AnyFloorplanData> {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`户型数据加载失败（${response.status}）：${detail}`)
  }
  return response.json() as Promise<AnyFloorplanData>
}

export async function saveFloorplan(data: AnyFloorplanData): Promise<{ uploadedAt: string }> {
  const response = await fetch(`/api/projects/${encodeURIComponent(data.project.id)}`, {
    method: 'PUT',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`保存失败（${response.status}）：${detail}`)
  }
  return response.json() as Promise<{ uploadedAt: string }>
}
