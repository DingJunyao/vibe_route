# 轨迹拆分参考信息重设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 轨迹拆分页移除自动切分，行政区划/道路信息改为聚合参考展示（可定位、可一键设切点），并恢复轨迹点悬停气泡。

**Architecture:** 区段只由手动切点决定。`trackSplitSegments.ts` 删除自动合并逻辑，新增"按维度值聚合出现区间"与"区段途经值摘要"两个纯函数；`TrackSplit.vue` 的"划分规则"面板重构为"参考信息"面板，"区段预览"去分组平铺；地图新增变化点标记并恢复 `point-hover` 气泡。后端无改动。

**Tech Stack:** Vue 3 + TypeScript + Element Plus；测试用 node:test 经 `npx tsx --test` 运行（无 vitest/jest）；类型检查用 `npm run build`（**勿用 `npm run build:check`，本机 vue-tsc 已损坏**，见 cc/changelog.md 2026-09 条目）。

**设计文档:** `docs/superpowers/specs/2026-09-13-track-split-reference-info-design.md`

---

### Task 1: utils 新增 `segmentValueSummary` 与 `aggregateRuns`

**Files:**
- Modify: `frontend/src/utils/trackSplitSegments.ts`
- Test: `frontend/tests/trackSplitSegments.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/tests/trackSplitSegments.test.ts` 的 import 块中加入 `aggregateRuns, segmentValueSummary`，并在文件末尾追加：

```ts
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx tsx --test tests/trackSplitSegments.test.ts`
Expected: FAIL，报 `segmentValueSummary` / `aggregateRuns` 不存在（导入错误）。

- [ ] **Step 3: 实现**

在 `frontend/src/utils/trackSplitSegments.ts` 中，`ContiguousSplitSegment` 接口之后新增：

```ts
export interface SplitValueAggregate {
  key: string
  label: string
  runCount: number
  pointCount: number
  distanceMeters: number
  runs: ContiguousSplitSegment[]
}
```

在 `buildContiguousSegments` 函数之后新增：

```ts
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx tsx --test tests/trackSplitSegments.test.ts`
Expected: PASS，7 个测试全过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/trackSplitSegments.ts frontend/tests/trackSplitSegments.test.ts
git commit -m "feat(track-split): add reference aggregation helpers

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: utils 新增 `buildSegmentsFromCuts`，删除自动切分逻辑

**Files:**
- Modify: `frontend/src/utils/trackSplitSegments.ts`
- Test: `frontend/tests/trackSplitSegments.test.ts`

- [ ] **Step 1: 改写测试**

`frontend/tests/trackSplitSegments.test.ts` 的 import 块改为（删 `mergeShortSegments, refineSegmentsWithCuts`，加 `buildSegmentsFromCuts`）：

```ts
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
```

将测试 `'manual cuts refine automatic segments without dropping source points'` 整体替换为：

```ts
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
  deepEqual(segments.map(segment => segment.label), ['E1', 'N1'])
})
```

将测试 `'a map cut immediately creates two boundaries and can be moved'` 中的

```ts
  deepEqual(
    refineSegmentsWithCuts([], cuts, Array.from({ length: 10 }, (_, index) => point({ index })), 'province')
      .map(segment => [segment.startIndex, segment.endIndex]),
```

改为：

```ts
  deepEqual(
    buildSegmentsFromCuts(cuts, Array.from({ length: 10 }, (_, index) => point({ index })), 'province')
      .map(segment => [segment.startIndex, segment.endIndex]),
```

将测试 `'short noisy runs merge into neighbors without dropping source points'` 整体删除。

在文件末尾追加一个多值摘要测试：

```ts
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx tsx --test tests/trackSplitSegments.test.ts`
Expected: FAIL，报 `buildSegmentsFromCuts` 不存在。

- [ ] **Step 3: 实现**

在 `frontend/src/utils/trackSplitSegments.ts` 中：

1. 删除 `const MIXED_LABEL = '混合区段'` 一行（`UNKNOWN_LABEL` 保留）。
2. 删除整个 `mergeShortSegments` 函数和整个 `refineSegmentsWithCuts` 函数。
3. 在 `aggregateRuns` 之后新增：

```ts
export function buildSegmentsFromCuts(
  cuts: number[],
  points: SplitSourcePoint[],
  mode: SplitGroupMode,
): ContiguousSplitSegment[] {
  if (points.length === 0) return []

  const orderedCuts = [...new Set(cuts)]
    .filter(cut => cut > 0 && cut < points.length)
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
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx tsx --test tests/trackSplitSegments.test.ts`
Expected: PASS，7 个测试全过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/utils/trackSplitSegments.ts frontend/tests/trackSplitSegments.test.ts
git commit -m "refactor(track-split): segments defined by manual cuts only

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: TrackSplit.vue script 重构

**Files:**
- Modify: `frontend/src/views/TrackSplit.vue`（`<script setup>` 部分）

本任务只改 script，模板在 Task 4 改。改完后模板会暂时引用不存在的变量，属预期，Task 4 结束后才构建。

- [ ] **Step 1: 更新 utils 导入**

将：

```ts
import {
  addManualCut,
  buildContiguousSegments,
  findNearestSplitPoint,
  mergeShortSegments,
  moveManualCut,
  refineSegmentsWithCuts,
  type ContiguousSplitSegment,
  type SplitGroupMode,
} from '@/utils/trackSplitSegments'
```

改为：

```ts
import {
  addManualCut,
  aggregateRuns,
  buildContiguousSegments,
  buildSegmentsFromCuts,
  findNearestSplitPoint,
  moveManualCut,
  type ContiguousSplitSegment,
  type SplitGroupMode,
  type SplitValueAggregate,
} from '@/utils/trackSplitSegments'
```

- [ ] **Step 2: 更新 vue 导入**

`import { computed, nextTick, onMounted, reactive, ref, shallowRef, watch } from 'vue'` 中删去 `watch`（三个 watcher 均将删除，无残留使用）。

- [ ] **Step 3: 删除 `SplitGroupView` 接口**

删除：

```ts
interface SplitGroupView {
  key: string
  label: string
  runCount: number
  pointCount: number
  distanceMeters: number
  segments: SplitSegmentView[]
}
```

- [ ] **Step 4: 替换状态声明**

将：

```ts
const autoGroup = ref(true)
const groupMode = ref<SplitGroupMode>('province')
const minimumSegmentPoints = ref(5)
const disabledAutoBoundaries = ref<Set<number>>(new Set())
const manualCuts = ref<number[]>([])
const selectedSegmentIds = ref<Set<string>>(new Set())
const segmentNames = reactive<Record<string, string>>({})
const groupQuery = ref('')
```

改为：

```ts
const referenceMode = ref<SplitGroupMode>('province')
const showChangeMarkers = ref(true)
const manualCuts = ref<number[]>([])
const selectedSegmentIds = ref<Set<string>>(new Set())
const segmentNames = reactive<Record<string, string>>({})
const aggregateQuery = ref('')
```

- [ ] **Step 5: 替换区段计算属性**

将 `automaticSegments`、`activeAutomaticSegments`、`workingSegments` 三个 computed 整体替换为：

```ts
const workingSegments = computed<ContiguousSplitSegment[]>(() =>
  buildSegmentsFromCuts(manualCuts.value, validPoints.value, referenceMode.value),
)

const referenceRuns = computed(() => buildContiguousSegments(validPoints.value, referenceMode.value))
```

- [ ] **Step 6: 替换分组计算属性**

将 `filteredGroups` 整个 computed 替换为：

```ts
const referenceAggregates = computed<SplitValueAggregate[]>(() => aggregateRuns(referenceRuns.value))

const filteredAggregates = computed<SplitValueAggregate[]>(() => {
  const query = aggregateQuery.value.trim().toLowerCase()
  if (!query) return referenceAggregates.value
  return referenceAggregates.value.filter(aggregate => aggregate.label.toLowerCase().includes(query))
})
```

- [ ] **Step 7: 简化切点状态标签**

将 `candidateStatusLabel` 改为：

```ts
const candidateStatusLabel = computed(() => {
  if (!candidatePoint.value) return ''
  return isManualCut.value ? '手动切点' : '未设切点'
})
```

将 `candidateMarkerLabel` 改为：

```ts
const candidateMarkerLabel = computed(() => {
  if (!candidatePoint.value) return ''
  return isManualCut.value ? '切点' : '当前点'
})
```

（`isSegmentBoundary` computed 保留，`handleMapClick`/`selectCandidateIndex` 仍以其为"已有边界"判断。）

- [ ] **Step 8: 简化 resetSegments 与 mergeIntoPrevious**

`resetSegments` 改为：

```ts
function resetSegments() {
  manualCuts.value = []
  focusedSegmentId.value = null
  Object.keys(segmentNames).forEach(key => delete segmentNames[key])
  selectSavableSegments()
}
```

`mergeIntoPrevious` 改为：

```ts
function mergeIntoPrevious(segment: SplitSegmentView) {
  if (segment.startIndex <= 0) return
  manualCuts.value = manualCuts.value.filter(cut => cut !== segment.startIndex)
  selectSavableSegments()
}
```

- [ ] **Step 9: 泛化定位函数并新增参考操作**

将 `segmentBounds` 改为按区间取值（`focusSegment` 相应改调用）：

```ts
function rangeBounds(startIndex: number, endIndex: number) {
  let minLat = Infinity
  let maxLat = -Infinity
  let minLon = Infinity
  let maxLon = -Infinity
  for (const point of validPoints.value.slice(startIndex, endIndex + 1)) {
    minLat = Math.min(minLat, point.latitude_wgs84)
    maxLat = Math.max(maxLat, point.latitude_wgs84)
    minLon = Math.min(minLon, point.longitude_wgs84)
    maxLon = Math.max(maxLon, point.longitude_wgs84)
  }
  return { minLat, maxLat, minLon, maxLon }
}

function focusSegment(segment: SplitSegmentView) {
  focusedSegmentId.value = segment.id
  mapRef.value?.fitToBounds?.(rangeBounds(segment.startIndex, segment.endIndex), 25)
}

function focusRun(run: ContiguousSplitSegment) {
  mapRef.value?.fitToBounds?.(rangeBounds(run.startIndex, run.endIndex), 25)
}

function isCutAt(index: number): boolean {
  return segmentBoundaryStarts.value.has(index)
}

function addCutAtRunStart(run: ContiguousSplitSegment) {
  if (validPoints.value.length === 0) return
  const nextCuts = addManualCut(
    manualCuts.value,
    run.startIndex,
    validPoints.value.length,
    [...segmentBoundaryStarts.value],
  )
  if (nextCuts === manualCuts.value) return
  manualCuts.value = nextCuts
  candidateIndex.value = run.startIndex
  selectSavableSegments()
  ElMessage.success('已添加切点')
}
```

- [ ] **Step 10: 删除三个 watcher**

删除：

```ts
watch(autoGroup, () => resetSegments())
watch(groupMode, () => resetSegments())
watch(minimumSegmentPoints, () => resetSegments())
```

- [ ] **Step 11: 提交**

```bash
git add frontend/src/views/TrackSplit.vue
git commit -m "refactor(track-split): reference info state in TrackSplit

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 参考信息面板与区段预览模板

**Files:**
- Modify: `frontend/src/views/TrackSplit.vue`（模板与样式，附一处 script 清理）

- [ ] **Step 0: 删除死代码 `isSegmentBoundary`**

Task 3 质量审查发现：`isSegmentBoundary` computed 在 script 与模板中均已无使用（`handleMapClick`/`selectCandidateIndex` 直接用 `segmentBoundaryStarts`）。从 `<script setup>` 删除该 computed（原 Task 3 Step 7 说明中"仍以其为判断"的表述有误，以此为准）。

- [ ] **Step 1: 替换"划分规则"面板**

将 `<section class="panel-block rules-panel">` 到对应 `</section>` 整段替换为：

```html
          <section class="panel-block reference-panel">
            <div class="panel-heading">
              <h2>参考信息</h2>
              <div class="reference-toggle">
                <span>标记变化点</span>
                <el-switch v-model="showChangeMarkers" size="small" />
              </div>
            </div>

            <el-select v-model="referenceMode" class="dimension-select">
              <el-option label="行政区划：省 / 州" value="province" />
              <el-option label="行政区划：市 / 县" value="city" />
              <el-option label="行政区划：区" value="district" />
              <el-option label="道路编号" value="roadNumber" />
              <el-option label="道路名称" value="roadName" />
            </el-select>

            <div class="rule-summary">
              <span>{{ filteredAggregates.length }} 个值</span>
              <span>{{ referenceRuns.length }} 个出现区间</span>
              <span>{{ manualCuts.length }} 个手动切点</span>
            </div>

            <el-input
              v-model="aggregateQuery"
              :prefix-icon="Search"
              clearable
              placeholder="搜索参考值"
              class="aggregate-search"
            />

            <div v-if="filteredAggregates.length === 0" class="list-empty">没有匹配的参考值</div>

            <div v-else class="aggregate-list">
              <article
                v-for="aggregate in filteredAggregates"
                :key="aggregate.key || 'unknown'"
                class="aggregate-item"
              >
                <header class="aggregate-header" @click="focusRun(aggregate.runs[0])">
                  <strong>{{ aggregate.label }}</strong>
                  <span>
                    {{ aggregate.runCount }} 次出现 · {{ formatNumber(aggregate.pointCount) }} 点 ·
                    {{ formatDistance(aggregate.distanceMeters) }}
                  </span>
                </header>
                <div
                  v-for="run in aggregate.runs"
                  :key="run.id"
                  class="run-row"
                  @click="focusRun(run)"
                >
                  <span class="run-range">
                    #{{ run.startIndex + 1 }} - #{{ run.endIndex + 1 }} ·
                    {{ run.pointCount }} 点 · {{ formatDistance(run.distanceMeters) }}
                  </span>
                  <el-button
                    v-if="run.startIndex > 0 && run.startIndex < points.length - 1"
                    size="small"
                    text
                    :type="isCutAt(run.startIndex) ? 'success' : 'primary'"
                    :disabled="isCutAt(run.startIndex)"
                    @click.stop="addCutAtRunStart(run)"
                  >
                    {{ isCutAt(run.startIndex) ? '已设切点' : '在此设切点' }}
                  </el-button>
                </div>
              </article>
            </div>
          </section>
```

- [ ] **Step 2: 替换"区段预览"面板**

将 `<section class="panel-block groups-panel">` 到对应 `</section>` 整段替换为（注意：全选/清空按钮从原"划分规则"面板移到此处标题行；卡片增加 `segment-summary` 一行；不再有分组包裹）：

```html
          <section class="panel-block segments-panel">
            <div class="panel-heading">
              <h2>区段预览</h2>
              <div class="segment-actions">
                <el-button size="small" @click="selectSavableSegments">全选可保存</el-button>
                <el-button size="small" @click="clearSelection">清空选择</el-button>
              </div>
            </div>

            <div class="segment-list">
              <div
                v-for="segment in segmentViews"
                :key="segment.id"
                class="segment-card"
                :class="{
                  selected: segment.selected,
                  focused: segment.id === focusedSegmentId,
                  disabled: !segment.savable,
                }"
                @click="focusSegment(segment)"
              >
                <div class="segment-card-body">
                  <div class="segment-card-main">
                    <el-checkbox
                      :model-value="segment.selected"
                      :disabled="!segment.savable || (!segment.selected && selectedSegments.length >= 100)"
                      label=""
                      @click.stop
                      @change="toggleSegment(segment)"
                    />
                    <div class="segment-copy">
                      <strong>区段 {{ segment.sequence }}</strong>
                      <span>
                        #{{ segment.startIndex + 1 }} - #{{ segment.endIndex + 1 }} ·
                        {{ segment.pointCount }} 点 · {{ formatDistance(segment.distanceMeters) }}
                      </span>
                      <span class="segment-summary">{{ segment.label }}</span>
                      <span>{{ formatTimeRange(segment.startTime, segment.endTime) }}</span>
                      <span v-if="!segment.savable" class="invalid-segment">少于 2 点，不能单独创建轨迹</span>
                    </div>
                  </div>

                  <el-input
                    v-model="segmentNames[segment.id]"
                    :placeholder="defaultSegmentName(segment)"
                    class="segment-name-input"
                    size="small"
                    @click.stop
                  />
                </div>

                <div class="segment-card-actions">
                  <el-tooltip content="定位到区段" placement="top">
                    <el-button :icon="Aim" circle size="small" @click.stop="focusSegment(segment)" />
                  </el-tooltip>
                  <el-tooltip
                    v-if="segment.startIndex > 0"
                    content="移除起点切点"
                    placement="top"
                  >
                    <el-button
                      :icon="ArrowUp"
                      circle
                      size="small"
                      @click.stop="mergeIntoPrevious(segment)"
                    />
                  </el-tooltip>
                </div>
              </div>
            </div>
          </section>
```

- [ ] **Step 3: 更新样式**

在 `<style scoped>` 中：

删除 `.group-search`、`.groups-empty`、`.group-list`、`.group-item`、`.group-header`、`.group-dot`、`.group-title` 相关规则。

新增（放在原 group 样式的位置）：

```css
.reference-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.aggregate-search {
  margin-top: 8px;
}

.list-empty {
  color: var(--el-text-color-secondary);
  padding: 12px 0;
  text-align: center;
}

.aggregate-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
}

.aggregate-item + .aggregate-item {
  border-top: 1px solid var(--el-border-color-extra-light);
  padding-top: 10px;
}

.aggregate-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  cursor: pointer;
}

.aggregate-header strong {
  font-size: 13px;
  overflow-wrap: anywhere;
}

.aggregate-header span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.run-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 6px;
  padding: 5px 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 5px;
  background: #f8fafc;
  cursor: pointer;
}

.run-range {
  min-width: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.segment-actions {
  display: flex;
  gap: 6px;
}

.segment-summary {
  color: var(--el-text-color-regular);
  font-weight: 500;
  overflow-wrap: anywhere;
}
```

`.segment-list` 样式保留（`margin-top: 8px` 一项可删，面板标题下已有间距，删除该行）。

- [ ] **Step 4: 构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无类型/模板错误（不得使用 `build:check`，见 Tech Stack）。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/TrackSplit.vue
git commit -m "feat(track-split): reference info panel replaces auto rules

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 地图变化点标记与气泡恢复

**Files:**
- Modify: `frontend/src/views/TrackSplit.vue`

- [ ] **Step 1: 恢复轨迹点悬停气泡**

删除 `UniversalMap` 上的 `:disable-point-hover="true"` 一行。

- [ ] **Step 2: 图例增加变化点**

在 `.map-legend` 的"当前切点"图例项之后追加：

```html
            <div class="legend-item">
              <span class="legend-dot change-dot"></span>
              <span>变化点</span>
            </div>
```

- [ ] **Step 3: 变化点覆盖层**

在 `mapOverlays` computed 中，`candidatePoint` 判断之前插入：

```ts
  if (showChangeMarkers.value) {
    for (const run of referenceRuns.value) {
      if (run.startIndex > 0 && !segmentBoundaryStarts.value.has(run.startIndex)) {
        overlays.push(makeMarker(validPoints.value[run.startIndex], '', '#0891b2', 5))
      }
    }
  }
```

（label 为空串：地图组件对 marker 以 `if (overlay.label)` 决定是否绘制文字，空串只渲染青色小圆点，与橙色切点圆点、深色边界圆点区分。）

- [ ] **Step 4: 样式**

在 `.candidate-dot` 规则后追加：

```css
.change-dot {
  background: #0891b2;
}
```

- [ ] **Step 5: 构建并提交**

Run: `cd frontend && npm run build`
Expected: 构建成功。

```bash
git add frontend/src/views/TrackSplit.vue
git commit -m "feat(track-split): change markers and point hover tooltip

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 浏览器验证与记录要点

**Files:**
- Modify: `cc/changelog.md`

- [ ] **Step 1: 浏览器验证**

开发者通常已在 Edge 打开 `http://localhost:5173`；用 edge-devtools MCP 操作验证（若未打开则先请开发者打开，不要自行起 Playwright）：

1. 打开一条跨多个行政区划的轨迹 → 进入"拆分轨迹"页。
2. 悬停轨迹点：出现与轨迹详情一致的气泡（时间/坐标/行政区划/道路）。
3. "参考信息"面板：默认"省/州"维度，聚合条目与实际数据一致；点击条目地图定位；点"在此设切点"后出现切点、按钮变"已设切点"。
4. 切换维度（市/县、道路编号）：聚合列表与地图青色变化点随之更新。
5. 点地图任意处添加切点、微调切点、移除切点：区段预览平铺列表、途经值摘要（如 `江苏 → 安徽`）正确。
6. 切换地图引擎（高德/百度/腾讯/Leaflet）重复 3-5 抽查：气泡、标记、定位正常。
7. 缩窄窗口到 ≤1366px：纵向堆叠布局正常。
8. **不要点击"按所选区段创建新轨迹"**——该操作写数据库，按 CLAUDE.md 由开发者自行验证。

- [ ] **Step 2: 记录要点**

在 `cc/changelog.md` 的 `## 2026-09` 列表末尾追加一条（跟随现有条目风格，简明记录）：

```markdown
- 轨迹拆分交互重设计：移除按行政区划/道路自动切分（及"最短区段点数"合并），区段完全由手动切点决定；右侧改为"参考信息"面板（五维聚合：值 × 出现次数/点数/距离，可点击定位、可一键在变化点设切点）；区段预览平铺并显示每段途经值摘要；地图新增青色变化点标记（可开关）、恢复轨迹点悬停气泡；`trackSplitSegments.ts` 删 `mergeShortSegments`/`refineSegmentsWithCuts`，新增 `segmentValueSummary`/`aggregateRuns`/`buildSegmentsFromCuts`（tsx --test 7 passed）。设计见 `docs/superpowers/specs/2026-09-13-track-split-reference-info-design.md`
```

- [ ] **Step 3: 提交**

```bash
git add cc/changelog.md
git commit -m "docs: record track split reference redesign notes

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Self-Review 记录

- **Spec 覆盖**：参考面板（Task 1/3/4）、一键设切点（Task 3/4）、区段平铺+摘要（Task 2/4）、变化点标记与开关（Task 3/5）、气泡恢复（Task 5）、搜索（Task 4）、并入上一区段语义（Task 3）、后端无改动（未列任务，符合）、移动端（Task 6 验证）、构建与浏览器验证（Task 4/5/6）、记录要点（Task 6）。无缺口。
- **占位符**：无 TBD/TODO；所有代码步骤均含完整代码。
- **类型一致性**：`buildSegmentsFromCuts(cuts, points, mode)`、`aggregateRuns(segments)`、`segmentValueSummary(points, startIndex, endIndex, mode)` 在 Task 1/2 定义、Task 3 调用签名一致；`SplitValueAggregate` 字段与 Task 4 模板（`label/runCount/pointCount/distanceMeters/runs`、`run.id/startIndex/endIndex/pointCount/distanceMeters`）一致。
