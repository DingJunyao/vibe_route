import { deepEqual, equal, ok } from 'node:assert'
import { test } from 'node:test'

import {
  addManualCut,
  aggregateRuns,
  buildContiguousSegments,
  findNearestSplitPoint,
  mergeShortSegments,
  moveManualCut,
  refineSegmentsWithCuts,
  segmentValueSummary,
  type SplitSourcePoint,
} from '../src/utils/trackSplitSegments.js'

function point(overrides: Partial<SplitSourcePoint> & { index: number }): SplitSourcePoint {
  return {
    longitude_wgs84: 106 + overrides.index * 0.001,
    latitude_wgs84: -6 + overrides.index * 0.001,
    province: null,
    city: null,
    district: null,
    road_number: null,
    road_name: null,
    ...overrides,
  }
}

test('contiguous grouping keeps repeated values as separate runs', () => {
  const points = [
    point({ index: 0, province: 'Jawa Barat' }),
    point({ index: 1, province: 'Jawa Barat' }),
    point({ index: 2, province: 'Banten' }),
    point({ index: 3 }),
    point({ index: 4, province: 'Banten' }),
  ]

  const segments = buildContiguousSegments(points, 'province')

  deepEqual(segments.map(segment => [segment.startIndex, segment.endIndex]), [
    [0, 1],
    [2, 2],
    [3, 3],
    [4, 4],
  ])
  deepEqual(segments.map(segment => segment.label), [
    'Jawa Barat',
    'Banten',
    '未识别',
    'Banten',
  ])
})

test('manual cuts refine automatic segments without dropping source points', () => {
  const points = [
    point({ index: 0, road_number: 'E1' }),
    point({ index: 1, road_number: 'E1' }),
    point({ index: 2, road_number: 'N1' }),
    point({ index: 3, road_number: 'N1' }),
    point({ index: 4, road_number: 'N1' }),
  ]
  const automatic = buildContiguousSegments(points, 'roadNumber')

  const refined = refineSegmentsWithCuts(automatic, [3], points, 'roadNumber')

  deepEqual(refined.map(segment => [segment.startIndex, segment.endIndex]), [
    [0, 1],
    [2, 2],
    [3, 4],
  ])
  equal(refined.reduce((sum, segment) => sum + segment.pointCount, 0), points.length)
})

test('a map cut immediately creates two boundaries and can be moved', () => {
  const cuts = addManualCut([], 4, 10, [])

  deepEqual(cuts, [4])
  deepEqual(
    refineSegmentsWithCuts([], cuts, Array.from({ length: 10 }, (_, index) => point({ index })), 'province')
      .map(segment => [segment.startIndex, segment.endIndex]),
    [
      [0, 3],
      [4, 9],
    ],
  )
  deepEqual(moveManualCut(cuts, 4, 6, 10, [4]), [6])
})

test('short noisy runs merge into neighbors without dropping source points', () => {
  const points = [
    point({ index: 0, road_number: 'E1' }),
    point({ index: 1, road_number: 'N1' }),
    point({ index: 2, road_number: 'E1' }),
    point({ index: 3, road_number: 'N2' }),
    point({ index: 4, road_number: 'N2' }),
    point({ index: 5, road_number: 'N2' }),
  ]
  const segments = buildContiguousSegments(points, 'roadNumber')

  const merged = mergeShortSegments(segments, points, 2, 'roadNumber')

  deepEqual(merged.map(segment => [segment.startIndex, segment.endIndex]), [
    [0, 2],
    [3, 5],
  ])
  equal(merged.reduce((sum, segment) => sum + segment.pointCount, 0), points.length)
  equal(merged[0].label, '混合区段')
})

test('nearest-point search uses the complete source sequence', () => {
  const points = [
    point({ index: 0 }),
    point({ index: 1 }),
    point({ index: 2 }),
  ]

  const nearest = findNearestSplitPoint(points, 106.0022, -5.9977)

  equal(nearest.index, 2)
  ok(nearest.distanceMeters > 0)
})

test('segment value summary dedupes values in first-seen order', () => {
  const points = [
    point({ index: 0, province: 'Jawa Barat' }),
    point({ index: 1, province: 'Banten' }),
    point({ index: 2, province: 'Banten' }),
    point({ index: 3, province: 'Jawa Barat' }),
    point({ index: 4 }),
  ]

  deepEqual(segmentValueSummary(points, 0, 4, 'province'), ['Jawa Barat', 'Banten', '未识别'])
  deepEqual(segmentValueSummary(points, 1, 2, 'province'), ['Banten'])
})

test('aggregateRuns groups repeated values with totals in first-seen order', () => {
  const points = [
    point({ index: 0, road_number: 'E1' }),
    point({ index: 1, road_number: 'N1' }),
    point({ index: 2, road_number: 'N1' }),
    point({ index: 3, road_number: 'E1' }),
  ]

  const aggregates = aggregateRuns(buildContiguousSegments(points, 'roadNumber'))

  equal(aggregates.length, 2)
  equal(aggregates[0].label, 'E1')
  equal(aggregates[0].runCount, 2)
  equal(aggregates[0].pointCount, 2)
  deepEqual(
    aggregates[0].runs.map(run => [run.startIndex, run.endIndex]),
    [[0, 0], [3, 3]],
  )
  equal(aggregates[1].label, 'N1')
  equal(aggregates[1].pointCount, 2)
  ok(aggregates[1].distanceMeters > 0)
})
