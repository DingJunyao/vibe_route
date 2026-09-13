import { deepEqual, equal, ok } from 'node:assert'
import { test } from 'node:test'

import {
  addManualCut,
  aggregateRuns,
  buildContiguousSegments,
  buildSegmentsFromCuts,
  findNearestSplitPoint,
  moveManualCut,
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

test('segments are defined by cuts only and summarize passed values', () => {
  const points = [
    point({ index: 0, road_number: 'E1' }),
    point({ index: 1, road_number: 'E1' }),
    point({ index: 2, road_number: 'N1' }),
    point({ index: 3, road_number: 'N1' }),
    point({ index: 4, road_number: 'E1' }),
  ]

  const segments = buildSegmentsFromCuts([3], points, 'roadNumber')

  deepEqual(segments.map(segment => [segment.startIndex, segment.endIndex]), [
    [0, 2],
    [3, 4],
  ])
  equal(segments.reduce((sum, segment) => sum + segment.pointCount, 0), points.length)
  deepEqual(segments.map(segment => segment.label), ['E1 → N1', 'N1 → E1'])
})

test('a map cut immediately creates two boundaries and can be moved', () => {
  const cuts = addManualCut([], 4, 10, [])

  deepEqual(cuts, [4])
  deepEqual(
    buildSegmentsFromCuts(cuts, Array.from({ length: 10 }, (_, index) => point({ index })), 'province')
      .map(segment => [segment.startIndex, segment.endIndex]),
    [
      [0, 3],
      [4, 9],
    ],
  )
  deepEqual(moveManualCut(cuts, 4, 6, 10, [4]), [6])
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

test('cut segments spanning multiple values get arrow summary labels', () => {
  const points = [
    point({ index: 0, province: 'Jawa Barat' }),
    point({ index: 1, province: 'Banten' }),
    point({ index: 2, province: 'Banten' }),
  ]

  const segments = buildSegmentsFromCuts([1], points, 'province')

  equal(segments.length, 2)
  equal(segments[0].label, 'Jawa Barat')
  equal(segments[1].label, 'Banten')

  const whole = buildSegmentsFromCuts([], points, 'province')
  equal(whole.length, 1)
  equal(whole[0].label, 'Jawa Barat → Banten')
})

test('aggregation helpers tolerate empty inputs', () => {
  deepEqual(segmentValueSummary([], 0, 0, 'province'), [])
  deepEqual(aggregateRuns([]), [])
})

test('adjacent unknown points form a single aggregate', () => {
  const points = [point({ index: 0 }), point({ index: 1 })]

  const aggregates = aggregateRuns(buildContiguousSegments(points, 'province'))

  equal(aggregates.length, 1)
  equal(aggregates[0].label, '未识别')
  equal(aggregates[0].pointCount, 2)
})

test('buildSegmentsFromCuts ignores invalid cut indices', () => {
  const points = [point({ index: 0 }), point({ index: 1 }), point({ index: 2 })]

  const segments = buildSegmentsFromCuts([-1, 0, 3, 99], points, 'province')

  equal(segments.length, 1)
  equal(segments[0].startIndex, 0)
  equal(segments[0].endIndex, 2)
})

test('buildSegmentsFromCuts tolerates empty points and duplicate cuts', () => {
  deepEqual(buildSegmentsFromCuts([2, 2], [], 'province'), [])
  const points = [point({ index: 0 }), point({ index: 1 }), point({ index: 2 })]
  const segments = buildSegmentsFromCuts([1, 1], points, 'province')
  equal(segments.length, 2)
  deepEqual(segments.map(segment => [segment.startIndex, segment.endIndex]), [[0, 0], [1, 2]])
})
