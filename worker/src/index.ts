import Ajv2020 from 'ajv/dist/2020'
import floorplanSchema from '../../schema/floorplan.schema.json'
import semanticFloorplanSchema from '../../schema/floorplan-v2.schema.json'

interface Env {
  FLOORPLANS: R2Bucket
  HMAC_SECRET: string
  EDITOR_TOKEN?: string
  ALLOWED_CLOCK_SKEW_SECONDS?: string
}

interface FloorplanPayloadV1 {
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

interface FloorplanPayloadV2 {
  schemaVersion: '2.0.0'
  project: { id: string }
  canvas: { width: number; height: number }
  templates: Array<{ id: string }>
  levels: Array<{
    id: string
    walls: Array<{ id: string; centerline: Array<[number, number]> }>
    openings: Array<{ id: string; wallId: string; segmentIndex: number; offset: number; width: number }>
    spaces: Array<{
      id: string
      boundary: Array<[number, number]>
      labelPosition: [number, number]
      boundaryStatus?: 'estimated' | 'verified'
      boundarySource?: 'generated' | 'manual'
      boundaryUpdatedAt?: string
    }>
    instances: Array<{ id: string; templateId: string; spaceId?: string }>
  }>
}

type FloorplanPayload = FloorplanPayloadV1 | FloorplanPayloadV2

interface ValidationIssue {
  instancePath: string
  message: string
}

const encoder = new TextEncoder()
const ajv = new Ajv2020({ allErrors: true, strict: false })
const validateV1Schema = ajv.compile(floorplanSchema)
const validateV2Schema = ajv.compile(semanticFloorplanSchema)
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

export function verifyEditorToken(request: Request, expectedToken?: string): boolean {
  if (!expectedToken) return false
  const authorization = request.headers.get('Authorization') ?? ''
  if (!authorization.startsWith('Bearer ')) return false
  const providedToken = authorization.slice('Bearer '.length)
  return safeEqual(providedToken, expectedToken)
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

function validateV1PayloadInvariants(value: FloorplanPayloadV1): ValidationIssue[] {
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

function validateV2PayloadInvariants(value: FloorplanPayloadV2): ValidationIssue[] {
  const errors: ValidationIssue[] = []
  const add = (instancePath: string, message: string) => errors.push({ instancePath, message })
  const duplicateTemplateIds = duplicateValues(value.templates.map((template) => template.id))
  if (duplicateTemplateIds.length) add('/templates', `contains duplicate ids: ${duplicateTemplateIds.join(', ')}`)
  const templateIds = new Set(value.templates.map((template) => template.id))
  const duplicateLevelIds = duplicateValues(value.levels.map((level) => level.id))
  if (duplicateLevelIds.length) add('/levels', `contains duplicate ids: ${duplicateLevelIds.join(', ')}`)

  for (const [levelIndex, level] of value.levels.entries()) {
    const prefix = `/levels/${levelIndex}`
    const allObjectIds = [
      ...level.walls.map((wall) => wall.id),
      ...level.openings.map((opening) => opening.id),
      ...level.spaces.map((space) => space.id),
      ...level.instances.map((instance) => instance.id),
    ]
    const duplicateObjectIds = duplicateValues(allObjectIds)
    if (duplicateObjectIds.length) add(prefix, `contains duplicate object ids: ${duplicateObjectIds.join(', ')}`)
    const walls = new Map(level.walls.map((wall) => [wall.id, wall]))
    const spaceIds = new Set(level.spaces.map((space) => space.id))

    for (const [openingIndex, opening] of level.openings.entries()) {
      const wall = walls.get(opening.wallId)
      const openingPath = `${prefix}/openings/${openingIndex}`
      if (!wall) {
        add(`${openingPath}/wallId`, `references unknown wall: ${opening.wallId}`)
        continue
      }
      if (opening.segmentIndex >= wall.centerline.length - 1) {
        add(`${openingPath}/segmentIndex`, 'must identify an existing wall segment')
        continue
      }
      const start = wall.centerline[opening.segmentIndex]
      const end = wall.centerline[opening.segmentIndex + 1]
      const segmentLength = Math.hypot(end[0] - start[0], end[1] - start[1])
      if (opening.offset + opening.width > segmentLength + 0.01) {
        add(openingPath, 'extends beyond its wall segment')
      }
    }

    for (const [instanceIndex, instance] of level.instances.entries()) {
      const instancePath = `${prefix}/instances/${instanceIndex}`
      if (!templateIds.has(instance.templateId)) add(`${instancePath}/templateId`, `references unknown template: ${instance.templateId}`)
      if (instance.spaceId && !spaceIds.has(instance.spaceId)) add(`${instancePath}/spaceId`, `references unknown space: ${instance.spaceId}`)
    }
  }
  return errors
}

export function validateFloorplanPayload(payload: unknown, projectId: string): { valid: true; value: FloorplanPayload } | { valid: false; errors: unknown } {
  const schemaVersion = (payload as { schemaVersion?: unknown } | null)?.schemaVersion
  const validateSchema = schemaVersion === '2.0.0' ? validateV2Schema : validateV1Schema
  if (!validateSchema(payload)) return { valid: false, errors: validateSchema.errors }
  const value = payload as unknown as FloorplanPayload
  if (value.project.id !== projectId) {
    return { valid: false, errors: [{ instancePath: '/project/id', message: 'must match URL project id' }] }
  }
  const invariantErrors = schemaVersion === '2.0.0'
    ? validateV2PayloadInvariants(value as FloorplanPayloadV2)
    : validateV1PayloadInvariants(value as FloorplanPayloadV1)
  if (invariantErrors.length) return { valid: false, errors: invariantErrors }
  return { valid: true, value }
}

export function preserveManualBoundaries(incoming: FloorplanPayloadV2, existing: FloorplanPayloadV2): FloorplanPayloadV2 {
  const existingLevels = new Map(existing.levels.map((level) => [level.id, level]))
  for (const incomingLevel of incoming.levels) {
    const existingLevel = existingLevels.get(incomingLevel.id)
    if (!existingLevel) continue
    const existingSpaces = new Map(existingLevel.spaces.map((space) => [space.id, space]))
    for (const incomingSpace of incomingLevel.spaces) {
      const existingSpace = existingSpaces.get(incomingSpace.id)
      if (existingSpace?.boundarySource !== 'manual' || incomingSpace.boundarySource === 'manual') continue
      incomingSpace.boundary = existingSpace.boundary
      incomingSpace.labelPosition = existingSpace.labelPosition
      incomingSpace.boundaryStatus = existingSpace.boundaryStatus
      incomingSpace.boundarySource = 'manual'
      incomingSpace.boundaryUpdatedAt = existingSpace.boundaryUpdatedAt
    }
  }
  return incoming
}

async function readProject(env: Env, projectId: string, headOnly = false): Promise<Response> {
  const object = await env.FLOORPLANS.get(`projects/${projectId}/floorplan.json`)
  if (object === null) return jsonResponse({ error: 'project_not_found' }, 404)
  const headers = new Headers()
  object.writeHttpMetadata(headers)
  headers.set('Content-Type', 'application/json; charset=utf-8')
  headers.set('Cache-Control', 'no-store')
  headers.set('ETag', object.httpEtag)
  headers.set('Content-Length', String(object.size))
  headers.set('X-Content-Type-Options', 'nosniff')
  return new Response(headOnly ? null : object.body, { headers })
}

async function writeProject(request: Request, env: Env, projectId: string): Promise<Response> {
  if (!env.HMAC_SECRET && !env.EDITOR_TOKEN) return jsonResponse({ error: 'write_not_configured' }, 503)
  const declaredLength = Number(request.headers.get('Content-Length') ?? 0)
  if (declaredLength > MAX_BODY_BYTES) return jsonResponse({ error: 'payload_too_large' }, 413)

  const body = await request.arrayBuffer()
  if (body.byteLength === 0) return jsonResponse({ error: 'empty_payload' }, 400)
  if (body.byteLength > MAX_BODY_BYTES) return jsonResponse({ error: 'payload_too_large' }, 413)
  const clockSkew = Number(env.ALLOWED_CLOCK_SKEW_SECONDS ?? 300)
  const authorized = verifyEditorToken(request, env.EDITOR_TOKEN)
    || Boolean(env.HMAC_SECRET && await verifyWriteSignature(request, body, env.HMAC_SECRET, clockSkew))
  if (!authorized) {
    return jsonResponse({ error: 'invalid_signature' }, 401)
  }

  let payload: unknown
  try {
    payload = JSON.parse(new TextDecoder().decode(body))
  } catch {
    return jsonResponse({ error: 'invalid_json' }, 400)
  }
  if ((payload as { schemaVersion?: unknown } | null)?.schemaVersion === '2.0.0') {
    const existingObject = await env.FLOORPLANS.get(`projects/${projectId}/floorplan.json`)
    if (existingObject) {
      try {
        const existingPayload = JSON.parse(await existingObject.text()) as FloorplanPayloadV2
        if (existingPayload.schemaVersion === '2.0.0') {
          payload = preserveManualBoundaries(payload as FloorplanPayloadV2, existingPayload)
        }
      } catch {
        // A corrupt previous object must not prevent replacing it with a valid upload.
      }
    }
  }
  const validation = validateFloorplanPayload(payload, projectId)
  if (!validation.valid) return jsonResponse({ error: 'schema_validation_failed', details: validation.errors }, 422)

  const storedBody = encoder.encode(JSON.stringify(payload))

  const uploadedAt = new Date().toISOString()
  await env.FLOORPLANS.put(`projects/${projectId}/floorplan.json`, storedBody, {
    httpMetadata: {
      contentType: 'application/json; charset=utf-8',
      cacheControl: 'no-store',
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
