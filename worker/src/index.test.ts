import { describe, expect, it } from 'vitest'
import { createWriteSignature, validateFloorplanPayload, verifyWriteSignature } from './index'

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
})
