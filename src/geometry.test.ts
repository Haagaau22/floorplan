import { describe, expect, it } from 'vitest'
import {
  cadToLocal,
  distanceMm,
  formatArea,
  formatDistance,
  localToCad,
  pointInPolygon,
  polygonAreaM2,
  polygonSelfIntersects,
  polygonsOverlap,
  polylineLengthMm,
  snapPointToBoundaries,
  wheelZoomFactor,
} from './geometry'

describe('CAD geometry', () => {
  it('keeps measurements in millimetres', () => {
    expect(distanceMm([0, 0], [3_000, 4_000])).toBe(5_000)
    expect(polylineLengthMm([[0, 0], [3_000, 0], [3_000, 4_000]])).toBe(7_000)
  })

  it('calculates polygon area in square metres', () => {
    expect(polygonAreaM2([[0, 0], [4_000, 0], [4_000, 3_000], [0, 3_000]])).toBe(12)
    expect(formatArea(12)).toBe('12.00 ㎡')
  })

  it('maps CAD y-up coordinates to SVG y-down coordinates without losing values', () => {
    const viewport = { minX: 1_000, minY: 2_000, maxX: 6_000, maxY: 8_000 }
    const local = cadToLocal([2_500, 6_500], viewport)
    expect(local).toEqual([1_500, 1_500])
    expect(localToCad(local, viewport)).toEqual([2_500, 6_500])
  })

  it('formats human readable distances', () => {
    expect(formatDistance(920)).toBe('920 mm')
    expect(formatDistance(2_500)).toBe('2.50 m')
    expect(formatDistance(15_000)).toBe('15.0 m')
  })

  it('keeps trackpad zoom gradual and bounded', () => {
    expect(wheelZoomFactor(10, 0, true)).toBeCloseTo(1.01, 3)
    expect(wheelZoomFactor(-10, 0, true)).toBeCloseTo(0.99, 3)
    expect(wheelZoomFactor(1_000)).toBeCloseTo(Math.exp(0.12), 6)
  })

  it('validates editable room polygons', () => {
    const room = [[0, 0], [4_000, 0], [4_000, 3_000], [0, 3_000]] as [number, number][]
    expect(pointInPolygon([2_000, 1_000], room)).toBe(true)
    expect(pointInPolygon([5_000, 1_000], room)).toBe(false)
    expect(polygonSelfIntersects([[0, 0], [4_000, 3_000], [0, 3_000], [4_000, 0]])).toBe(true)
  })

  it('allows shared walls but rejects overlapping ownership regions', () => {
    const first = [[0, 0], [2_000, 0], [2_000, 2_000], [0, 2_000]] as [number, number][]
    const adjacent = [[2_000, 0], [4_000, 0], [4_000, 2_000], [2_000, 2_000]] as [number, number][]
    const overlap = [[1_500, 0], [3_000, 0], [3_000, 2_000], [1_500, 2_000]] as [number, number][]
    expect(polygonsOverlap(first, adjacent)).toBe(false)
    expect(polygonsOverlap(first, overlap)).toBe(true)
  })

  it('snaps an edited vertex to nearby room walls and adjacent axes', () => {
    expect(snapPointToBoundaries([1_970, 1_020], [[[2_000, 0], [2_000, 3_000]]], [[0, 1_000]], 60)).toEqual([2_000, 1_000])
  })
})
