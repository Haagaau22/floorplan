import type { LocalViewBox, Point, Viewport } from './types'

export function distanceMm(a: Point, b: Point): number {
  return Math.hypot(b[0] - a[0], b[1] - a[1])
}

export function polylineLengthMm(points: Point[], closed = false): number {
  if (points.length < 2) return 0
  let total = 0
  for (let index = 1; index < points.length; index += 1) {
    total += distanceMm(points[index - 1], points[index])
  }
  if (closed && points.length > 2) total += distanceMm(points.at(-1)!, points[0])
  return total
}

export function polygonAreaM2(points: Point[]): number {
  if (points.length < 3) return 0
  let twiceArea = 0
  for (let index = 0; index < points.length; index += 1) {
    const [x1, y1] = points[index]
    const [x2, y2] = points[(index + 1) % points.length]
    twiceArea += x1 * y2 - x2 * y1
  }
  return Math.abs(twiceArea) / 2_000_000
}

function pointOnSegment(point: Point, start: Point, end: Point, tolerance = 0.001): boolean {
  const cross = (point[0] - start[0]) * (end[1] - start[1]) - (point[1] - start[1]) * (end[0] - start[0])
  if (Math.abs(cross) > tolerance) return false
  return point[0] >= Math.min(start[0], end[0]) - tolerance
    && point[0] <= Math.max(start[0], end[0]) + tolerance
    && point[1] >= Math.min(start[1], end[1]) - tolerance
    && point[1] <= Math.max(start[1], end[1]) + tolerance
}

export function pointInPolygon(point: Point, polygon: Point[], includeBoundary = true): boolean {
  if (polygon.length < 3) return false
  let inside = false
  for (let index = 0; index < polygon.length; index += 1) {
    const start = polygon[index]
    const end = polygon[(index + 1) % polygon.length]
    if (pointOnSegment(point, start, end)) return includeBoundary
    if ((start[1] > point[1]) !== (end[1] > point[1])) {
      const crossingX = start[0] + (point[1] - start[1]) * (end[0] - start[0]) / (end[1] - start[1])
      if (crossingX > point[0]) inside = !inside
    }
  }
  return inside
}

function orientation(first: Point, second: Point, third: Point): number {
  return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (third[0] - first[0])
}

function segmentsProperlyIntersect(firstStart: Point, firstEnd: Point, secondStart: Point, secondEnd: Point): boolean {
  const a = orientation(firstStart, firstEnd, secondStart)
  const b = orientation(firstStart, firstEnd, secondEnd)
  const c = orientation(secondStart, secondEnd, firstStart)
  const d = orientation(secondStart, secondEnd, firstEnd)
  return ((a > 0 && b < 0) || (a < 0 && b > 0)) && ((c > 0 && d < 0) || (c < 0 && d > 0))
}

export function polygonSelfIntersects(polygon: Point[]): boolean {
  for (let first = 0; first < polygon.length; first += 1) {
    const firstNext = (first + 1) % polygon.length
    for (let second = first + 1; second < polygon.length; second += 1) {
      const secondNext = (second + 1) % polygon.length
      if (first === second || firstNext === second || secondNext === first) continue
      if (segmentsProperlyIntersect(polygon[first], polygon[firstNext], polygon[second], polygon[secondNext])) return true
    }
  }
  return false
}

export function polygonsOverlap(first: Point[], second: Point[]): boolean {
  for (let firstIndex = 0; firstIndex < first.length; firstIndex += 1) {
    const firstEnd = first[(firstIndex + 1) % first.length]
    for (let secondIndex = 0; secondIndex < second.length; secondIndex += 1) {
      const secondEnd = second[(secondIndex + 1) % second.length]
      if (segmentsProperlyIntersect(first[firstIndex], firstEnd, second[secondIndex], secondEnd)) return true
    }
  }
  if (first.some((point) => pointInPolygon(point, second, false))) return true
  if (second.some((point) => pointInPolygon(point, first, false))) return true
  const firstMidpoints = first.map((point, index): Point => [
    (point[0] + first[(index + 1) % first.length][0]) / 2,
    (point[1] + first[(index + 1) % first.length][1]) / 2,
  ])
  const secondMidpoints = second.map((point, index): Point => [
    (point[0] + second[(index + 1) % second.length][0]) / 2,
    (point[1] + second[(index + 1) % second.length][1]) / 2,
  ])
  if (firstMidpoints.some((point) => pointInPolygon(point, second, false))) return true
  if (secondMidpoints.some((point) => pointInPolygon(point, first, false))) return true
  return pointInPolygon(polygonCentroid(first), second, false) || pointInPolygon(polygonCentroid(second), first, false)
}

export function polygonCentroid(polygon: Point[]): Point {
  if (polygon.length === 0) return [0, 0]
  let areaTwice = 0
  let xTotal = 0
  let yTotal = 0
  for (let index = 0; index < polygon.length; index += 1) {
    const current = polygon[index]
    const next = polygon[(index + 1) % polygon.length]
    const cross = current[0] * next[1] - next[0] * current[1]
    areaTwice += cross
    xTotal += (current[0] + next[0]) * cross
    yTotal += (current[1] + next[1]) * cross
  }
  if (Math.abs(areaTwice) < 0.001) {
    return [
      Math.round(polygon.reduce((total, point) => total + point[0], 0) / polygon.length),
      Math.round(polygon.reduce((total, point) => total + point[1], 0) / polygon.length),
    ]
  }
  return [Math.round(xTotal / (3 * areaTwice)), Math.round(yTotal / (3 * areaTwice))]
}

export function nearestPointOnSegment(point: Point, start: Point, end: Point): Point {
  const dx = end[0] - start[0]
  const dy = end[1] - start[1]
  if (dx === 0 && dy === 0) return [...start]
  const ratio = Math.max(0, Math.min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)))
  return [start[0] + dx * ratio, start[1] + dy * ratio]
}

export function snapPointToBoundaries(point: Point, boundaries: Point[][], adjacent: Point[], tolerance: number): Point {
  let snapped: Point = [...point]
  for (const neighbor of adjacent) {
    if (Math.abs(snapped[0] - neighbor[0]) <= tolerance) snapped[0] = neighbor[0]
    if (Math.abs(snapped[1] - neighbor[1]) <= tolerance) snapped[1] = neighbor[1]
  }

  let bestDistance = tolerance
  for (const boundary of boundaries) {
    for (let index = 0; index < boundary.length; index += 1) {
      const candidate = nearestPointOnSegment(snapped, boundary[index], boundary[(index + 1) % boundary.length])
      const candidateDistance = distanceMm(snapped, candidate)
      if (candidateDistance <= bestDistance) {
        snapped = candidate
        bestDistance = candidateDistance
      }
    }
  }
  return [Math.round(snapped[0]), Math.round(snapped[1])]
}

export function cadToLocal(point: Point, viewport: Viewport): Point {
  return [point[0] - viewport.minX, viewport.maxY - point[1]]
}

export function localToCad(point: Point, viewport: Viewport): Point {
  return [point[0] + viewport.minX, viewport.maxY - point[1]]
}

function compact(value: number): string {
  return Number(value.toFixed(3)).toString()
}

export function pointsToPath(points: Point[], viewport: Viewport, closed = false): string {
  if (points.length === 0) return ''
  const [firstX, firstY] = cadToLocal(points[0], viewport)
  const commands = [`M${compact(firstX)} ${compact(firstY)}`]
  for (const point of points.slice(1)) {
    const [x, y] = cadToLocal(point, viewport)
    commands.push(`L${compact(x)} ${compact(y)}`)
  }
  if (closed) commands.push('Z')
  return commands.join('')
}

export function clampViewBox(viewBox: LocalViewBox, drawingWidth: number, drawingHeight: number): LocalViewBox {
  const width = Math.min(Math.max(viewBox.width, drawingWidth / 80), drawingWidth * 1.5)
  const height = Math.min(Math.max(viewBox.height, drawingHeight / 80), drawingHeight * 1.5)
  const marginX = width * 0.2
  const marginY = height * 0.2
  return {
    x: Math.min(Math.max(viewBox.x, -marginX), drawingWidth - width + marginX),
    y: Math.min(Math.max(viewBox.y, -marginY), drawingHeight - height + marginY),
    width,
    height,
  }
}

export function wheelZoomFactor(deltaY: number, deltaMode = 0, isTrackpadPinch = false): number {
  const pixels = deltaMode === 1 ? deltaY * 16 : deltaMode === 2 ? deltaY * 800 : deltaY
  const clampedDelta = Math.min(Math.max(pixels, -80), 80)
  const sensitivity = isTrackpadPinch ? 0.001 : 0.0015
  return Math.exp(clampedDelta * sensitivity)
}

export function formatDistance(mm: number): string {
  if (mm < 1_000) return `${Math.round(mm)} mm`
  return `${(mm / 1_000).toFixed(mm < 10_000 ? 2 : 1)} m`
}

export function formatArea(areaM2: number): string {
  return `${areaM2.toFixed(2)} ㎡`
}
