import Ajv2020 from 'ajv/dist/2020'
import floorplanSchema from '../../schema/floorplan.schema.json'

interface Env {
  FLOORPLANS: R2Bucket
  HMAC_SECRET: string
  ALLOWED_CLOCK_SKEW_SECONDS?: string
}

interface FloorplanPayload {
  schemaVersion: string
  project: { id: string }
  viewport: { minX: number; minY: number; maxX: number; maxY: number }
  layers: Array<{ id: string; entityCount: number }>
  entities: Array<{
    id: string
    kind: 'path' | 'text'
    layerId: string
    points?: Array<[number, number]>
  }>
  spaces: Array<{ id: string; label: string; type: 'room' | 'corridor' }>
  dimensions: Array<{ id: string }>
  statistics: {
    exportedEntities: number
    pathCount: number
    textCount: number
    vertexCount: number
    spaceCount: number
  }
}

interface ValidationIssue {
  instancePath: string
  message: string
}

const encoder = new TextEncoder()
const ajv = new Ajv2020({ allErrors: true, strict: false })
const validateSchema = ajv.compile(floorplanSchema)
const projectRoute = /^\/api\/projects\/([a-z0-9][a-z0-9-]*)$/
const MAX_BODY_BYTES = 15 * 1024 * 1024

function jsonResponse(payload: unknown, status = 200, headers: HeadersInit = {}): Response {
  return Response.json(payload, {
    status,
    headers: {
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      ...headers,
    },
  })
}

function bytesToHex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)].map((value) => value.toString(16).padStart(2, '0')).join('')
}

async function sha256Hex(body: ArrayBuffer): Promise<string> {
  return bytesToHex(await crypto.subtle.digest('SHA-256', body))
}

function safeEqual(first: string, second: string): boolean {
  if (first.length !== second.length) return false
  let result = 0
  for (let index = 0; index < first.length; index += 1) {
    result |= first.charCodeAt(index) ^ second.charCodeAt(index)
  }
  return result === 0
}

export async function createWriteSignature(
  secret: string,
  method: string,
  pathname: string,
  timestamp: string,
  body: ArrayBuffer,
): Promise<string> {
  const bodyHash = await sha256Hex(body)
  const message = `${method.toUpperCase()}\n${pathname}\n${timestamp}\n${bodyHash}`
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  )
  return bytesToHex(await crypto.subtle.sign('HMAC', key, encoder.encode(message)))
}

export async function verifyWriteSignature(
  request: Request,
  body: ArrayBuffer,
  secret: string,
  allowedClockSkewSeconds = 300,
  nowSeconds = Math.floor(Date.now() / 1_000),
): Promise<boolean> {
  const timestamp = request.headers.get('X-Floorplan-Timestamp') ?? ''
  const signature = request.headers.get('X-Floorplan-Signature')?.toLowerCase() ?? ''
  if (!/^\d{10}$/.test(timestamp) || !/^[a-f0-9]{64}$/.test(signature)) return false
  if (Math.abs(nowSeconds - Number(timestamp)) > allowedClockSkewSeconds) return false
  const expected = await createWriteSignature(secret, request.method, new URL(request.url).pathname, timestamp, body)
  return safeEqual(signature, expected)
}

function duplicateValues(values: string[]): string[] {
  const seen = new Set<string>()
  const duplicates = new Set<string>()
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value)
    seen.add(value)
  }
  return [...duplicates]
}

function validatePayloadInvariants(value: FloorplanPayload): ValidationIssue[] {
  const errors: ValidationIssue[] = []
  const add = (instancePath: string, message: string) => errors.push({ instancePath, message })
  const viewport = value.viewport
  if (viewport.minX >= viewport.maxX || viewport.minY >= viewport.maxY) {
    add('/viewport', 'must have increasing min/max coordinates')
  }

  const duplicateLayerIds = duplicateValues(value.layers.map((layer) => layer.id))
  if (duplicateLayerIds.length) add('/layers', `contains duplicate ids: ${duplicateLayerIds.join(', ')}`)
  const layerIds = new Set(value.layers.map((layer) => layer.id))
  const unknownLayerIds = [...new Set(value.entities.map((entity) => entity.layerId).filter((id) => !layerIds.has(id)))]
  if (unknownLayerIds.length) add('/entities', `references unknown layers: ${unknownLayerIds.join(', ')}`)

  const duplicateEntityIds = duplicateValues(value.entities.map((entity) => entity.id))
  if (duplicateEntityIds.length) add('/entities', `contains duplicate ids: ${duplicateEntityIds.join(', ')}`)
  const duplicateSpaceIds = duplicateValues(value.spaces.map((space) => space.id))
  if (duplicateSpaceIds.length) add('/spaces', `contains duplicate ids: ${duplicateSpaceIds.join(', ')}`)
  const duplicateRoomLabels = duplicateValues(value.spaces.filter((space) => space.type === 'room').map((space) => space.label))
  if (duplicateRoomLabels.length) add('/spaces', `contains duplicate room labels: ${duplicateRoomLabels.join(', ')}`)
  const duplicateDimensionIds = duplicateValues(value.dimensions.map((dimension) => dimension.id))
  if (duplicateDimensionIds.length) add('/dimensions', `contains duplicate ids: ${duplicateDimensionIds.join(', ')}`)

  const actualLayerCounts = new Map<string, number>()
  for (const entity of value.entities) {
    actualLayerCounts.set(entity.layerId, (actualLayerCounts.get(entity.layerId) ?? 0) + 1)
  }
  for (const layer of value.layers) {
    const actual = actualLayerCounts.get(layer.id) ?? 0
    if (layer.entityCount !== actual) add(`/layers/${layer.id}/entityCount`, `declares ${layer.entityCount}, actual ${actual}`)
  }

  const actualStatistics = {
    exportedEntities: value.entities.length,
    pathCount: value.entities.filter((entity) => entity.kind === 'path').length,
    textCount: value.entities.filter((entity) => entity.kind === 'text').length,
    vertexCount: value.entities.reduce((total, entity) => total + (entity.kind === 'path' ? entity.points!.length : 0), 0),
    spaceCount: value.spaces.length,
  }
  for (const [name, actual] of Object.entries(actualStatistics)) {
    const declared = value.statistics[name as keyof typeof actualStatistics]
    if (declared !== actual) add(`/statistics/${name}`, `declares ${declared}, actual ${actual}`)
  }
  return errors
}

export function validateFloorplanPayload(payload: unknown, projectId: string): { valid: true; value: FloorplanPayload } | { valid: false; errors: unknown } {
  if (!validateSchema(payload)) {
    return { valid: false, errors: validateSchema.errors }
  }
  const value = payload as unknown as FloorplanPayload
  if (value.project.id !== projectId) {
    return { valid: false, errors: [{ instancePath: '/project/id', message: 'must match URL project id' }] }
  }
  const invariantErrors = validatePayloadInvariants(value)
  if (invariantErrors.length) return { valid: false, errors: invariantErrors }
  return { valid: true, value }
}

async function readProject(env: Env, projectId: string, headOnly = false): Promise<Response> {
  const object = await env.FLOORPLANS.get(`projects/${projectId}/floorplan.json`)
  if (object === null) return jsonResponse({ error: 'project_not_found' }, 404)
  const headers = new Headers()
  object.writeHttpMetadata(headers)
  headers.set('Content-Type', 'application/json; charset=utf-8')
  headers.set('Cache-Control', 'public, max-age=60, stale-while-revalidate=300')
  headers.set('ETag', object.httpEtag)
  headers.set('Content-Length', String(object.size))
  headers.set('X-Content-Type-Options', 'nosniff')
  return new Response(headOnly ? null : object.body, { headers })
}

async function writeProject(request: Request, env: Env, projectId: string): Promise<Response> {
  if (!env.HMAC_SECRET) return jsonResponse({ error: 'write_not_configured' }, 503)
  const declaredLength = Number(request.headers.get('Content-Length') ?? 0)
  if (declaredLength > MAX_BODY_BYTES) return jsonResponse({ error: 'payload_too_large' }, 413)

  const body = await request.arrayBuffer()
  if (body.byteLength === 0) return jsonResponse({ error: 'empty_payload' }, 400)
  if (body.byteLength > MAX_BODY_BYTES) return jsonResponse({ error: 'payload_too_large' }, 413)
  const clockSkew = Number(env.ALLOWED_CLOCK_SKEW_SECONDS ?? 300)
  if (!await verifyWriteSignature(request, body, env.HMAC_SECRET, clockSkew)) {
    return jsonResponse({ error: 'invalid_signature' }, 401)
  }

  let payload: unknown
  try {
    payload = JSON.parse(new TextDecoder().decode(body))
  } catch {
    return jsonResponse({ error: 'invalid_json' }, 400)
  }
  const validation = validateFloorplanPayload(payload, projectId)
  if (!validation.valid) return jsonResponse({ error: 'schema_validation_failed', details: validation.errors }, 422)

  const uploadedAt = new Date().toISOString()
  await env.FLOORPLANS.put(`projects/${projectId}/floorplan.json`, body, {
    httpMetadata: {
      contentType: 'application/json; charset=utf-8',
      cacheControl: 'public, max-age=60, stale-while-revalidate=300',
    },
    customMetadata: {
      schemaVersion: validation.value.schemaVersion,
      uploadedAt,
    },
  })
  return jsonResponse({ ok: true, projectId, schemaVersion: validation.value.schemaVersion, uploadedAt })
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url)
    const match = projectRoute.exec(url.pathname)
    if (!match) return jsonResponse({ error: 'not_found' }, 404)
    const projectId = match[1]

    if (request.method === 'GET' || request.method === 'HEAD') return readProject(env, projectId, request.method === 'HEAD')
    if (request.method === 'PUT') return writeProject(request, env, projectId)
    return jsonResponse({ error: 'method_not_allowed' }, 405, { Allow: 'GET, HEAD, PUT' })
  },
} satisfies ExportedHandler<Env>
