import { describe, expect, it } from 'vitest'
import { createWriteSignature, preserveManualBoundaries, validateFloorplanPayload, verifyWriteSignature } from './index'

const secret = 'test-only-secret-with-enough-entropy'
const timestamp = '1794900000'

async function signedRequest(body: ArrayBuffer): Promise<Request> {
  const path = '/api/projects/apartment'
  const signature = await createWriteSignature(secret, 'PUT', path, timestamp, body)
  return new Request(`https://floorplan.example${path}`, {
    method: 'PUT',
    headers: {
      'X-Floorplan-Timestamp': timestamp,
      'X-Floorplan-Signature': signature,
    },
    body,
  })
}

describe('Worker HMAC writes', () => {
  it('accepts an intact request inside the clock window', async () => {
    const body = new TextEncoder().encode('{"project":"apartment"}').buffer
    const request = await signedRequest(body)
    await expect(verifyWriteSignature(request, body, secret, 300, Number(timestamp))).resolves.toBe(true)
  })

  it('rejects payload tampering', async () => {
    const original = new TextEncoder().encode('{"value":1}').buffer
    const tampered = new TextEncoder().encode('{"value":2}').buffer
    const request = await signedRequest(original)
    await expect(verifyWriteSignature(request, tampered, secret, 300, Number(timestamp))).resolves.toBe(false)
  })

  it('rejects expired signatures', async () => {
    const body = new TextEncoder().encode('{}').buffer
    const request = await signedRequest(body)
    await expect(verifyWriteSignature(request, body, secret, 300, Number(timestamp) + 301)).resolves.toBe(false)
  })
})

describe('manual boundary preservation', () => {
  it('keeps a browser-confirmed boundary during a later generated upload', () => {
    const existing = {
      schemaVersion: '2.0.0' as const,
      project: { id: 'apartment' }, canvas: { width: 10, height: 10 }, templates: [],
      levels: [{ id: 'level-01', walls: [], openings: [], instances: [], spaces: [{
        id: 'room-3', boundary: [[0, 0], [5, 0], [5, 5]] as [number, number][], labelPosition: [2, 2] as [number, number],
        boundaryStatus: 'verified' as const, boundarySource: 'manual' as const, boundaryUpdatedAt: '2026-11-18T00:00:00Z',
      }] }],
    }
    const incoming = {
      schemaVersion: '2.0.0' as const,
      project: { id: 'apartment' }, canvas: { width: 10, height: 10 }, templates: [],
      levels: [{ id: 'level-01', walls: [], openings: [], instances: [], spaces: [{
        id: 'room-3', boundary: [[0, 0], [9, 0], [9, 9]] as [number, number][], labelPosition: [4, 4] as [number, number], boundarySource: 'generated' as const,
      }] }],
    }
    const merged = preserveManualBoundaries(incoming, existing)
    expect(merged.levels[0].spaces[0]).toMatchObject({
      boundary: [[0, 0], [5, 0], [5, 5]],
      labelPosition: [2, 2],
      boundarySource: 'manual',
    })
  })
})

function validPayload() {
  return {
    schemaVersion: '1.0.0',
    project: {
      id: 'apartment',
      name: 'Test',
      source: 'test.dxf',
      generatedAt: '2026-11-17T00:00:00Z',
      status: 'working-baseline',
    },
    coordinateSystem: { units: 'mm', xAxis: 'right', yAxis: 'up', origin: [0, 0] },
    viewport: { minX: 0, minY: 0, maxX: 100, maxY: 100 },
    layers: [{ id: 'linework', name: 'Lines', defaultVisible: true, entityCount: 1 }],
    entities: [{ id: 'path-1', kind: 'path', layerId: 'linework', points: [[0, 0], [100, 100]], closed: false }],
    spaces: [{
      id: 'room-1',
      label: '1',
      type: 'room',
      labelPosition: [50, 50],
      selectionBoundary: [[0, 0], [100, 0], [100, 100]],
      boundaryStatus: 'selection-region',
      metrics: { areaM2: null, perimeterM: null },
      business: {},
      verification: { status: 'needs-review', note: 'test' },
    }],
    dimensions: [],
    statistics: {
      sourceEntities: 1,
      exportedEntities: 1,
      pathCount: 1,
      textCount: 0,
      vertexCount: 2,
      spaceCount: 1,
    },
  }
}

describe('Worker project validation', () => {
  it('accepts a schema-valid project with consistent references and counts', () => {
    expect(validateFloorplanPayload(validPayload(), 'apartment').valid).toBe(true)
  })

  it('rejects unknown layer references', () => {
    const payload = validPayload()
    payload.entities[0].layerId = 'missing'
    expect(validateFloorplanPayload(payload, 'apartment')).toMatchObject({ valid: false })
  })

  it('rejects statistics that do not describe the drawing', () => {
    const payload = validPayload()
    payload.statistics.vertexCount = 99
    expect(validateFloorplanPayload(payload, 'apartment')).toMatchObject({ valid: false })
  })

  it('accepts a self-contained semantic v2 project', () => {
    const payload = {
      schemaVersion: '2.0.0',
      project: { id: 'apartment', name: 'Semantic', status: 'verified' },
      coordinateSystem: { units: 'mm', xAxis: 'right', yAxis: 'down' },
      canvas: { width: 5000, height: 4000 },
      templates: [{
        id: 'bed', name: 'Bed', category: 'furniture', size: { width: 1800, depth: 2000 }, anchor: [900, 1000],
        geometry: { paths: [{ points: [[0, 0], [1800, 0], [1800, 2000], [0, 2000]], closed: true }] },
      }],
      levels: [{
        id: 'level-01', name: 'Level 1',
        walls: [{ id: 'wall-1', kind: 'interior', centerline: [[0, 0], [5000, 0]], thickness: 120 }],
        openings: [{ id: 'door-1', kind: 'door', wallId: 'wall-1', segmentIndex: 0, offset: 1000, width: 900 }],
        spaces: [{ id: 'room-1', kind: 'room', name: 'Room', boundary: [[0, 0], [5000, 0], [5000, 4000]], labelPosition: [2500, 2000] }],
        instances: [{ id: 'bed-1', templateId: 'bed', position: [2500, 2000], spaceId: 'room-1' }],
      }],
    }
    expect(validateFloorplanPayload(payload, 'apartment').valid).toBe(true)
  })

  it('rejects semantic v2 references to unknown templates', () => {
    const payload = {
      schemaVersion: '2.0.0',
      project: { id: 'apartment', name: 'Semantic', status: 'draft' },
      coordinateSystem: { units: 'mm', xAxis: 'right', yAxis: 'down' },
      canvas: { width: 100, height: 100 },
      templates: [],
      levels: [{ id: 'level-01', name: 'Level', walls: [], openings: [], spaces: [], instances: [{ id: 'item-1', templateId: 'missing', position: [0, 0] }] }],
    }
    expect(validateFloorplanPayload(payload, 'apartment')).toMatchObject({ valid: false })
  })
})
