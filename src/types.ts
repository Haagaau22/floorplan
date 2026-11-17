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
