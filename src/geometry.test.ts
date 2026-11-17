import { describe, expect, it } from 'vitest'
import {
  cadToLocal,
  distanceMm,
  formatArea,
  formatDistance,
  localToCad,
  polygonAreaM2,
  polylineLengthMm,
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
})
