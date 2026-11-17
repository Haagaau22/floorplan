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

export function formatDistance(mm: number): string {
  if (mm < 1_000) return `${Math.round(mm)} mm`
  return `${(mm / 1_000).toFixed(mm < 10_000 ? 2 : 1)} m`
}

export function formatArea(areaM2: number): string {
  return `${areaM2.toFixed(2)} ㎡`
}
