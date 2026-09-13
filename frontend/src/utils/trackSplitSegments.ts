export type SplitGroupMode = 'province' | 'city' | 'district' | 'roadNumber' | 'roadName'

export interface SplitSourcePoint {
  longitude_wgs84: number
  latitude_wgs84: number
  province?: string | null
  city?: string | null
  district?: string | null
  road_number?: string | null
  road_name?: string | null
}

export interface ContiguousSplitSegment {
  id: string
  startIndex: number
  endIndex: number
  pointCount: number
  key: string
  label: string
  distanceMeters: number
}

export interface SplitValueAggregate {
  key: string
  label: string
  runCount: number
  pointCount: number
  distanceMeters: number
  runs: ContiguousSplitSegment[]
}

const UNKNOWN_LABEL = '未识别'

function normalized(value: string | null | undefined): string {
  const result = value?.trim()
  return result ? result : ''
}

function groupKeyAndLabel(point: SplitSourcePoint, mode: SplitGroupMode): [string, string] {
  if (mode === 'province') {
    const value = normalized(point.province)
    return value ? [value, value] : ['', UNKNOWN_LABEL]
  }

  if (mode === 'city') {
    const province = normalized(point.province)
    const city = normalized(point.city)
    return city ? [`${province}||${city}`, [province, city].filter(Boolean).join(' / ')] : ['', UNKNOWN_LABEL]
  }

  if (mode === 'district') {
    const province = normalized(point.province)
    const city = normalized(point.city)
    const district = normalized(point.district)
    return district
      ? [`${province}||${city}||${district}`, [province, city, district].filter(Boolean).join(' / ')]
      : ['', UNKNOWN_LABEL]
  }

  if (mode === 'roadNumber') {
    const value = normalized(point.road_number)
    return value ? [value, value] : ['', UNKNOWN_LABEL]
  }

  const value = normalized(point.road_name)
  return value ? [value, value] : ['', UNKNOWN_LABEL]
}

export function distanceBetweenPoints(
  from: Pick<SplitSourcePoint, 'latitude_wgs84' | 'longitude_wgs84'>,
  to: Pick<SplitSourcePoint, 'latitude_wgs84' | 'longitude_wgs84'>,
): number {
  const earthRadius = 6371000
  const latRad = (degrees: number) => degrees * Math.PI / 180
  const dLat = latRad(to.latitude_wgs84 - from.latitude_wgs84)
  const dLon = latRad(to.longitude_wgs84 - from.longitude_wgs84)
  const lat1 = latRad(from.latitude_wgs84)
  const lat2 = latRad(to.latitude_wgs84)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * earthRadius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function makeSegment(
  points: SplitSourcePoint[],
  startIndex: number,
  endIndex: number,
  mode: SplitGroupMode,
): ContiguousSplitSegment {
  const segmentPoints = points.slice(startIndex, endIndex + 1)
  const [key, label] = groupKeyAndLabel(segmentPoints[0], mode)
  let distanceMeters = 0
  for (let index = 1; index < segmentPoints.length; index += 1) {
    distanceMeters += distanceBetweenPoints(segmentPoints[index - 1], segmentPoints[index])
  }
  return {
    id: `${startIndex}-${endIndex}`,
    startIndex,
    endIndex,
    pointCount: segmentPoints.length,
    key,
    label,
    distanceMeters,
  }
}

export function buildContiguousSegments(
  points: SplitSourcePoint[],
  mode: SplitGroupMode,
): ContiguousSplitSegment[] {
  if (points.length === 0) return []

  const segments: ContiguousSplitSegment[] = []
  let startIndex = 0
  let currentKey = groupKeyAndLabel(points[0], mode)[0]
  for (let index = 1; index < points.length; index += 1) {
    const key = groupKeyAndLabel(points[index], mode)[0]
    if (key !== currentKey) {
      segments.push(makeSegment(points, startIndex, index - 1, mode))
      startIndex = index
      currentKey = key
    }
  }
  segments.push(makeSegment(points, startIndex, points.length - 1, mode))
  return segments
}

export function segmentValueSummary(
  points: SplitSourcePoint[],
  startIndex: number,
  endIndex: number,
  mode: SplitGroupMode,
): string[] {
  const labels: string[] = []
  for (const point of points.slice(startIndex, endIndex + 1)) {
    const label = groupKeyAndLabel(point, mode)[1]
    if (!labels.includes(label)) labels.push(label)
  }
  return labels
}

export function aggregateRuns(segments: ContiguousSplitSegment[]): SplitValueAggregate[] {
  const aggregates: SplitValueAggregate[] = []
  const aggregateMap = new Map<string, SplitValueAggregate>()
  for (const segment of segments) {
    let aggregate = aggregateMap.get(segment.key)
    if (!aggregate) {
      aggregate = {
        key: segment.key,
        label: segment.label,
        runCount: 0,
        pointCount: 0,
        distanceMeters: 0,
        runs: [],
      }
      aggregateMap.set(segment.key, aggregate)
      aggregates.push(aggregate)
    }
    aggregate.runCount += 1
    aggregate.pointCount += segment.pointCount
    aggregate.distanceMeters += segment.distanceMeters
    aggregate.runs.push(segment)
  }
  return aggregates
}

export function buildSegmentsFromCuts(
  cuts: number[],
  points: SplitSourcePoint[],
  mode: SplitGroupMode,
): ContiguousSplitSegment[] {
  if (points.length === 0) return []

  const orderedCuts = [...new Set(cuts)]
    .filter(cut => isValidCut(cut, points.length))
    .sort((a, b) => a - b)

  const segments: ContiguousSplitSegment[] = []
  let previousBoundary = 0
  for (const cut of orderedCuts) {
    segments.push(makeSegment(points, previousBoundary, cut - 1, mode))
    previousBoundary = cut
  }
  segments.push(makeSegment(points, previousBoundary, points.length - 1, mode))

  for (const segment of segments) {
    const summary = segmentValueSummary(points, segment.startIndex, segment.endIndex, mode)
    segment.key = segment.id
    segment.label = summary.length > 1 ? summary.join(' → ') : (summary[0] || UNKNOWN_LABEL)
  }
  return segments
}

function isValidCut(index: number, pointCount: number): boolean {
  return Number.isInteger(index) && index > 0 && index < pointCount
}

export function addManualCut(
  cuts: number[],
  index: number,
  pointCount: number,
  existingBoundaries: number[],
): number[] {
  if (!isValidCut(index, pointCount) || existingBoundaries.includes(index)) return cuts
  return [...new Set([...cuts, index])].sort((a, b) => a - b)
}

export function moveManualCut(
  cuts: number[],
  from: number,
  to: number,
  pointCount: number,
  existingBoundaries: number[],
): number[] {
  if (!cuts.includes(from) || !isValidCut(to, pointCount)) return cuts
  if (existingBoundaries.includes(to) || cuts.includes(to)) return cuts
  return cuts
    .map(cut => cut === from ? to : cut)
    .sort((a, b) => a - b)
}

export function findNearestSplitPoint(
  points: SplitSourcePoint[],
  longitude: number,
  latitude: number,
): { index: number; distanceMeters: number } {
  let nearestIndex = -1
  let nearestDistance = Infinity
  const target = { latitude_wgs84: latitude, longitude_wgs84: longitude }
  points.forEach((point, index) => {
    const distance = distanceBetweenPoints(target, point)
    if (distance < nearestDistance) {
      nearestDistance = distance
      nearestIndex = index
    }
  })
  return { index: nearestIndex, distanceMeters: nearestDistance }
}
