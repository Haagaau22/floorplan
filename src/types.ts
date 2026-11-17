export type Point = [number, number]

export interface Viewport {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export interface FloorplanLayer {
  id: string
  name: string
  defaultVisible: boolean
  entityCount: number
}

export interface PathEntity {
  id: string
  kind: 'path'
  layerId: string
  points: Point[]
  closed: boolean
}

export interface TextEntity {
  id: string
  kind: 'text'
  layerId: string
  position: Point
  content: string
  height: number
  rotation: number
}

export type DrawingEntity = PathEntity | TextEntity

export interface SpaceBusinessData {
  bathroomAreaM2?: number | null
  bathroomPerimeterM?: number | null
  closedKitchen?: boolean
  closedKitchenAreaM2?: number | null
  kitchenWallLengthM?: number | null
  floorTile?: string
  wallTile?: string
  [key: string]: unknown
}

export interface FloorplanSpace {
  id: string
  label: string
  type: 'room' | 'corridor'
  labelPosition: Point
  selectionBoundary: Point[]
  boundaryStatus: 'selection-region' | 'verified'
  metrics: {
    areaM2: number | null
    perimeterM: number | null
  }
  business: SpaceBusinessData
  verification: {
    status: 'estimated' | 'verified' | 'needs-review'
    note: string
  }
}

export interface CadDimension {
  id: string
  measurement: number
  start: Point
  end: Point
  textOverride?: string
}

export interface FloorplanData {
  schemaVersion: string
  project: {
    id: string
    name: string
    source: string
    sourceDrawing?: string
    generatedAt: string
    status: 'working-baseline' | 'verified'
    statusNote?: string
  }
  coordinateSystem: {
    units: 'mm'
    xAxis: 'right'
    yAxis: 'up'
    origin: Point
  }
  viewport: Viewport
  layers: FloorplanLayer[]
  entities: DrawingEntity[]
  spaces: FloorplanSpace[]
  dimensions: CadDimension[]
  statistics: {
    sourceEntities: number
    exportedEntities: number
    pathCount: number
    textCount: number
    vertexCount: number
    spaceCount: number
  }
}

export type ToolMode = 'pan' | 'distance' | 'area'

export interface LocalViewBox {
  x: number
  y: number
  width: number
  height: number
}

export interface SemanticPath {
  points: Point[]
  closed: boolean
  role?: 'outline' | 'detail' | 'fill'
}

export interface SemanticTemplate {
  id: string
  name: string
  category: 'furniture' | 'fixture' | 'equipment' | 'circulation'
  size: { width: number; depth: number }
  anchor: Point
  geometry: {
    paths: SemanticPath[]
    circles?: Array<{ center: Point; radius: number; role?: 'outline' | 'detail' | 'fill' }>
  }
  source?: {
    kind: 'project' | 'catalog' | 'generated'
    name?: string
    url?: string
    license?: string
  }
}

export interface SemanticWall {
  id: string
  kind: 'exterior' | 'interior' | 'partition'
  centerline: Point[]
  thickness: number
  height?: number
}

export interface SemanticOpening {
  id: string
  kind: 'door' | 'window' | 'passage'
  wallId: string
  segmentIndex: number
  offset: number
  width: number
  swing?: 'none' | 'left-in' | 'right-in' | 'left-out' | 'right-out'
}

export interface SemanticSpace {
  id: string
  kind: 'apartment' | 'room' | 'corridor' | 'utility' | 'electrical' | 'plumbing' | 'stair' | 'elevator' | 'common' | 'outdoor' | 'excluded' | 'void'
  name: string
  number?: string
  boundary: Point[]
  labelPosition: Point
  labelStyle?: 'room-tag' | 'area-name' | 'hidden'
  boundaryStatus?: 'estimated' | 'verified'
}

export interface SemanticInstance {
  id: string
  templateId: string
  position: Point
  rotation?: number
  scale?: Point
  spaceId?: string
}

export interface SemanticLevel {
  id: string
  name: string
  elevation?: number
  walls: SemanticWall[]
  openings: SemanticOpening[]
  spaces: SemanticSpace[]
  instances: SemanticInstance[]
  details?: SemanticPath[]
}

export interface SemanticFloorplanData {
  schemaVersion: '2.0.0'
  project: {
    id: string
    name: string
    status: 'draft' | 'review' | 'verified'
    source?: string
    notes?: string
  }
  coordinateSystem: {
    units: 'mm'
    xAxis: 'right'
    yAxis: 'down'
  }
  canvas: { width: number; height: number }
  templates: SemanticTemplate[]
  levels: SemanticLevel[]
}

export type AnyFloorplanData = FloorplanData | SemanticFloorplanData

export function isSemanticFloorplan(data: AnyFloorplanData): data is SemanticFloorplanData {
  return data.schemaVersion === '2.0.0'
}
