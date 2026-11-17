<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { saveFloorplan } from '../api'
import {
  clampViewBox,
  distanceMm,
  formatArea,
  formatDistance,
  pointInPolygon,
  polygonAreaM2,
  polygonCentroid,
  polygonSelfIntersects,
  polygonsOverlap,
  snapPointToBoundaries,
  wheelZoomFactor,
} from '../geometry'
import type { LocalViewBox, Point, SemanticFloorplanData, SemanticOpening, SemanticSpace, ToolMode } from '../types'
import BoundaryEditorPanel from './BoundaryEditorPanel.vue'
import IconGlyph from './IconGlyph.vue'
import SemanticInfoPanel from './SemanticInfoPanel.vue'

const props = defineProps<{ data: SemanticFloorplanData }>()
const workingData = ref<SemanticFloorplanData>(jsonClone(props.data))
const level = workingData.value.levels[0]
const drawingWidth = workingData.value.canvas.width
const drawingHeight = workingData.value.canvas.height
const svgRef = ref<SVGSVGElement>()
const viewBox = ref<LocalViewBox>({ x: 0, y: 0, width: drawingWidth, height: drawingHeight })
const mode = ref<ToolMode>('pan')
const selectedSpaceId = ref<string>()
const measurementPoints = ref<Point[]>([])
const layerMenuOpen = ref(false)
const panelOpen = ref(false)
const didDrag = ref(false)
const layerVisibility = ref({ structure: true, templates: true, labels: true, zones: true })
const activeVertex = ref<number>()
const dragVertex = ref<number>()
const editPast = ref<SemanticSpace[][]>([])
const editFuture = ref<SemanticSpace[][]>([])
const savedSpaces = ref(JSON.stringify(level.spaces))
const creatingSpace = ref<{ name: string; kind: SemanticSpace['kind'] }>()
const draftBoundary = ref<Point[]>([])
const saving = ref(false)
const saveMessage = ref('')
const pointers = new Map<number, { x: number; y: number }>()
let previousPinchDistance = 0

function jsonClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const templates = new Map(workingData.value.templates.map((template) => [template.id, template]))
const walls = new Map(level.walls.map((wall) => [wall.id, wall]))
const selectedSpace = computed(() => level.spaces.find((space) => space.id === selectedSpaceId.value))
const svgViewBox = computed(() => `${viewBox.value.x} ${viewBox.value.y} ${viewBox.value.width} ${viewBox.value.height}`)
const labelScale = computed(() => viewBox.value.width / 30_000)
const detailsPath = computed(() => (level.details ?? []).map((item) => pathD(item.points, item.closed)).join(' '))
const measurementPath = computed(() => pathD(measurementPoints.value, mode.value === 'area' && measurementPoints.value.length > 2))
const distanceResult = computed(() => measurementPoints.value.length === 2 ? distanceMm(measurementPoints.value[0], measurementPoints.value[1]) : null)
const areaResult = computed(() => measurementPoints.value.length > 2 ? polygonAreaM2(measurementPoints.value) : null)
const regularSpaces = computed(() => level.spaces.filter((space) => space.kind !== 'excluded'))
const excludedSpaces = computed(() => level.spaces.filter((space) => space.kind === 'excluded'))
const interactiveSpaces = computed(() => mode.value === 'edit' ? level.spaces : regularSpaces.value)
const editDirty = computed(() => JSON.stringify(level.spaces) !== savedSpaces.value)
const editIssues = computed(() => {
  const issues: string[] = []
  for (const space of level.spaces) {
    const label = space.number ? `${space.number}号房` : space.name
    if (space.boundary.length < 3) issues.push(`${label} 少于 3 个边界点`)
    else if (polygonAreaM2(space.boundary) < 0.01) issues.push(`${label} 的区域面积无效`)
    else if (polygonSelfIntersects(space.boundary)) issues.push(`${label} 的边界发生自相交`)
    if (!pointInPolygon(space.labelPosition, space.boundary)) issues.push(`${label} 的标签落在区域外`)
  }
  for (let first = 0; first < level.spaces.length; first += 1) {
    for (let second = first + 1; second < level.spaces.length; second += 1) {
      if (polygonsOverlap(level.spaces[first].boundary, level.spaces[second].boundary)) {
        issues.push(`${level.spaces[first].name} 与 ${level.spaces[second].name} 发生重叠`)
      }
    }
  }
  return issues
})

function pathD(points: Point[], closed: boolean) {
  if (!points.length) return ''
  return `M ${points.map((point) => `${point[0]} ${point[1]}`).join(' L ')}${closed ? ' Z' : ''}`
}

function pointsAttribute(points: Point[]) {
  return points.map((point) => point.join(',')).join(' ')
}

function openingGeometry(opening: SemanticOpening) {
  const wall = walls.get(opening.wallId)!
  const start = wall.centerline[opening.segmentIndex]
  const end = wall.centerline[opening.segmentIndex + 1]
  const length = Math.hypot(end[0] - start[0], end[1] - start[1])
  const at = (distance: number): Point => {
    const ratio = length ? distance / length : 0
    return [start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio]
  }
  const first = at(opening.offset)
  const second = at(opening.offset + opening.width)
  const dx = second[0] - first[0]
  const dy = second[1] - first[1]
  const side = opening.swing?.includes('out') ? -1 : 1
  const leaf: Point = [first[0] - dy * side, first[1] + dx * side]
  return { wall, first, second, leaf, length: opening.width, sweep: side > 0 ? 1 : 0 }
}

function setMode(nextMode: ToolMode) {
  mode.value = nextMode
  measurementPoints.value = []
  layerMenuOpen.value = false
  if (nextMode !== 'edit') {
    activeVertex.value = undefined
    dragVertex.value = undefined
    creatingSpace.value = undefined
    draftBoundary.value = []
  } else {
    layerVisibility.value.zones = true
  }
}

function cloneSpaces(): SemanticSpace[] {
  return jsonClone(level.spaces)
}

function recordEdit() {
  editPast.value.push(cloneSpaces())
  if (editPast.value.length > 80) editPast.value.shift()
  editFuture.value = []
  saveMessage.value = ''
}

function restoreSpaces(spaces: SemanticSpace[]) {
  level.spaces = jsonClone(spaces)
  if (selectedSpaceId.value && !level.spaces.some((space) => space.id === selectedSpaceId.value)) selectedSpaceId.value = undefined
  activeVertex.value = undefined
}

function undoEdit() {
  const previous = editPast.value.pop()
  if (!previous) return
  editFuture.value.push(cloneSpaces())
  restoreSpaces(previous)
}

function redoEdit() {
  const next = editFuture.value.pop()
  if (!next) return
  editPast.value.push(cloneSpaces())
  restoreSpaces(next)
}

function snapEditPoint(point: Point, space?: SemanticSpace, vertexIndex?: number): Point {
  const boundaries = level.spaces.filter((item) => item.id !== space?.id).map((item) => item.boundary)
  const adjacent: Point[] = []
  if (space && vertexIndex != null && space.boundary.length > 2) {
    adjacent.push(
      space.boundary[(vertexIndex - 1 + space.boundary.length) % space.boundary.length],
      space.boundary[(vertexIndex + 1) % space.boundary.length],
    )
  }
  return snapPointToBoundaries(point, boundaries, adjacent, Math.max(45, viewBox.value.width / 260))
}

function markBoundaryManual(space: SemanticSpace) {
  space.boundaryStatus = 'verified'
  space.boundarySource = 'manual'
  space.boundaryUpdatedAt = new Date().toISOString()
}

function startVertexDrag(event: PointerEvent, index: number) {
  if (!selectedSpace.value) return
  event.stopPropagation()
  event.preventDefault()
  recordEdit()
  didDrag.value = false
  activeVertex.value = index
  dragVertex.value = index
  svgRef.value?.setPointerCapture(event.pointerId)
}

function insertVertexOnEdge(event: MouseEvent, edgeIndex: number) {
  const space = selectedSpace.value
  if (!space) return
  event.stopPropagation()
  recordEdit()
  const point = snapEditPoint(eventToLocal(event), space, edgeIndex)
  space.boundary.splice(edgeIndex + 1, 0, point)
  markBoundaryManual(space)
  activeVertex.value = edgeIndex + 1
}

function addVertex() {
  const space = selectedSpace.value
  if (!space) return
  recordEdit()
  const startIndex = activeVertex.value ?? space.boundary.length - 1
  const start = space.boundary[startIndex]
  const end = space.boundary[(startIndex + 1) % space.boundary.length]
  space.boundary.splice(startIndex + 1, 0, [Math.round((start[0] + end[0]) / 2), Math.round((start[1] + end[1]) / 2)])
  markBoundaryManual(space)
  activeVertex.value = startIndex + 1
}

function deleteVertex() {
  const space = selectedSpace.value
  if (!space || activeVertex.value == null || space.boundary.length <= 3) return
  recordEdit()
  space.boundary.splice(activeVertex.value, 1)
  markBoundaryManual(space)
  activeVertex.value = undefined
}

function beginCreateSpace(name: string, kind: SemanticSpace['kind']) {
  creatingSpace.value = { name, kind }
  draftBoundary.value = []
  activeVertex.value = undefined
  selectedSpaceId.value = undefined
}

function finishCreateSpace() {
  if (!creatingSpace.value || draftBoundary.value.length < 3) return
  recordEdit()
  const boundary = jsonClone(draftBoundary.value)
  const idSuffix = `${Date.now()}`
  const space: SemanticSpace = {
    id: `manual-${creatingSpace.value.kind}-${idSuffix}`,
    kind: creatingSpace.value.kind,
    name: creatingSpace.value.name,
    boundary,
    labelPosition: polygonCentroid(boundary),
    labelStyle: creatingSpace.value.kind === 'excluded' ? 'area-name' : 'area-name',
    boundaryStatus: 'verified',
    boundarySource: 'manual',
    boundaryUpdatedAt: new Date().toISOString(),
  }
  level.spaces.push(space)
  selectedSpaceId.value = space.id
  creatingSpace.value = undefined
  draftBoundary.value = []
}

function cancelCreateSpace() {
  creatingSpace.value = undefined
  draftBoundary.value = []
}

async function saveEdits() {
  if (!editDirty.value || editIssues.value.length) return
  saving.value = true
  saveMessage.value = ''
  try {
    const result = await saveFloorplan(workingData.value)
    savedSpaces.value = JSON.stringify(level.spaces)
    saveMessage.value = `已保存 · ${new Date(result.uploadedAt).toLocaleString('zh-CN', { hour12: false })}`
  } catch (error) {
    saveMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    saving.value = false
  }
}

function fitDrawing() {
  viewBox.value = { x: 0, y: 0, width: drawingWidth, height: drawingHeight }
}

function zoomAt(factor: number, localX = viewBox.value.x + viewBox.value.width / 2, localY = viewBox.value.y + viewBox.value.height / 2) {
  const current = viewBox.value
  const width = current.width * factor
  const height = current.height * factor
  const xRatio = (localX - current.x) / current.width
  const yRatio = (localY - current.y) / current.height
  viewBox.value = clampViewBox({ x: localX - width * xRatio, y: localY - height * yRatio, width, height }, drawingWidth, drawingHeight)
}

function eventToLocal(event: { clientX: number; clientY: number }): Point {
  const matrix = svgRef.value?.getScreenCTM()
  if (matrix) {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse())
    return [point.x, point.y]
  }
  return [0, 0]
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  const [x, y] = eventToLocal(event)
  zoomAt(wheelZoomFactor(event.deltaY, event.deltaMode, event.ctrlKey), x, y)
}

function onPointerDown(event: PointerEvent) {
  svgRef.value?.setPointerCapture(event.pointerId)
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY })
  didDrag.value = false
  if (pointers.size === 2) {
    const values = [...pointers.values()]
    previousPinchDistance = Math.hypot(values[1].x - values[0].x, values[1].y - values[0].y)
  }
}

function onPointerMove(event: PointerEvent) {
  if (mode.value === 'edit' && dragVertex.value != null && selectedSpace.value) {
    const point = snapEditPoint(eventToLocal(event), selectedSpace.value, dragVertex.value)
    selectedSpace.value.boundary.splice(dragVertex.value, 1, point)
    markBoundaryManual(selectedSpace.value)
    didDrag.value = true
    return
  }
  const previous = pointers.get(event.pointerId)
  if (!previous) return
  const current = { x: event.clientX, y: event.clientY }
  pointers.set(event.pointerId, current)
  if (pointers.size === 2) {
    const values = [...pointers.values()]
    const distance = Math.hypot(values[1].x - values[0].x, values[1].y - values[0].y)
    if (previousPinchDistance > 0 && distance > 0) {
      const [x, y] = eventToLocal({ clientX: (values[0].x + values[1].x) / 2, clientY: (values[0].y + values[1].y) / 2 })
      zoomAt(Math.pow(previousPinchDistance / distance, 0.55), x, y)
      didDrag.value = true
    }
    previousPinchDistance = distance
    return
  }
  if (mode.value !== 'pan') return
  const [previousX, previousY] = eventToLocal({ clientX: previous.x, clientY: previous.y })
  const [currentX, currentY] = eventToLocal({ clientX: current.x, clientY: current.y })
  if (Math.abs(current.x - previous.x) + Math.abs(current.y - previous.y) > 1) didDrag.value = true
  viewBox.value = clampViewBox({ ...viewBox.value, x: viewBox.value.x - (currentX - previousX), y: viewBox.value.y - (currentY - previousY) }, drawingWidth, drawingHeight)
}

function onPointerUp(event: PointerEvent) {
  dragVertex.value = undefined
  pointers.delete(event.pointerId)
  if (pointers.size < 2) previousPinchDistance = 0
}

function onCanvasClick(event: MouseEvent) {
  if (didDrag.value || mode.value === 'pan') return
  const point = eventToLocal(event)
  if (mode.value === 'edit') {
    if (creatingSpace.value) draftBoundary.value = [...draftBoundary.value, snapEditPoint(point)]
  } else if (mode.value === 'distance') {
    measurementPoints.value = measurementPoints.value.length >= 2 ? [point] : [...measurementPoints.value, point]
  } else {
    measurementPoints.value = [...measurementPoints.value, point]
  }
}

function selectSpace(space: SemanticSpace) {
  selectedSpaceId.value = space.id
  activeVertex.value = undefined
  panelOpen.value = true
  if (mode.value === 'edit') return
  const width = Math.min(viewBox.value.width, drawingWidth / 3.2)
  const height = width * drawingHeight / drawingWidth
  viewBox.value = clampViewBox({ x: space.labelPosition[0] - width / 2, y: space.labelPosition[1] - height / 2, width, height }, drawingWidth, drawingHeight)
}

function selectSpaceById(id: string) {
  const space = level.spaces.find((item) => item.id === id)
  if (space) selectSpace(space)
}

function onKeydown(event: KeyboardEvent) {
  if (mode.value === 'edit' && (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    if (event.shiftKey) redoEdit()
    else undoEdit()
    return
  }
  if (mode.value === 'edit' && (event.key === 'Delete' || event.key === 'Backspace') && activeVertex.value != null) {
    event.preventDefault()
    deleteVertex()
    return
  }
  if (event.key === 'Escape') {
    measurementPoints.value = []
    if (creatingSpace.value) cancelCreateSpace()
    else selectedSpaceId.value = undefined
  }
  if (event.key === '+' || event.key === '=') zoomAt(0.82)
  if (event.key === '-') zoomAt(1.18)
  if (event.key.toLowerCase() === 'f') fitDrawing()
}

window.addEventListener('keydown', onKeydown)
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="viewer-shell semantic-viewer">
    <section class="drawing-stage" :class="`mode-${mode}`">
      <header class="viewer-header">
        <div class="brand-lockup">
          <span class="brand-mark">FP</span>
          <div><strong>Floorplan</strong><span>Semantic JSON Viewer</span></div>
        </div>
        <div class="header-project"><span>JSON v{{ workingData.schemaVersion }}</span><strong>{{ workingData.project.name }}</strong></div>
        <button class="mobile-info-button" type="button" @click="panelOpen = true">项目 / 空间</button>
      </header>

      <div class="canvas-wrap">
        <svg
          ref="svgRef"
          class="floorplan-svg semantic-svg"
          :viewBox="svgViewBox"
          role="img"
          :aria-label="workingData.project.name"
          tabindex="0"
          @wheel="onWheel"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
          @click="onCanvasClick"
        >
          <defs>
            <g v-for="template in data.templates" :id="`semantic-template-${template.id}`" :key="template.id">
              <path v-for="(path, index) in template.geometry.paths" :key="`p-${index}`" :d="pathD(path.points, path.closed)" :class="`template-${path.role ?? 'outline'}`" />
              <circle v-for="(circle, index) in template.geometry.circles ?? []" :key="`c-${index}`" :cx="circle.center[0]" :cy="circle.center[1]" :r="circle.radius" :class="`template-${circle.role ?? 'outline'}`" />
            </g>
          </defs>
          <rect class="drawing-paper" x="0" y="0" :width="drawingWidth" :height="drawingHeight" />

          <g v-show="layerVisibility.zones" class="semantic-zones">
            <polygon v-for="space in excludedSpaces" :key="space.id" :points="pointsAttribute(space.boundary)" class="semantic-excluded" />
          </g>

          <g class="semantic-space-hits">
            <path
              v-for="space in interactiveSpaces"
              :key="space.id"
              :d="pathD(space.boundary, true)"
              :class="['space-hit', { 'space-hit--selected': selectedSpace?.id === space.id }]"
              tabindex="0" role="button" :aria-label="space.name"
              @click.stop="selectSpace(space)" @keydown.enter.stop="selectSpace(space)"
            />
          </g>

          <g v-show="layerVisibility.structure" class="semantic-structure">
            <path v-if="detailsPath" :d="detailsPath" class="semantic-details" />
            <polyline v-for="wall in level.walls" :key="wall.id" :points="pointsAttribute(wall.centerline)" :stroke-width="wall.thickness" class="semantic-wall" />
            <template v-for="opening in level.openings" :key="opening.id">
              <line
                :x1="openingGeometry(opening).first[0]" :y1="openingGeometry(opening).first[1]"
                :x2="openingGeometry(opening).second[0]" :y2="openingGeometry(opening).second[1]"
                :stroke-width="openingGeometry(opening).wall.thickness + 24" class="semantic-opening-cut"
              />
              <line
                v-if="opening.kind === 'window'"
                :x1="openingGeometry(opening).first[0]" :y1="openingGeometry(opening).first[1]"
                :x2="openingGeometry(opening).second[0]" :y2="openingGeometry(opening).second[1]" class="semantic-window"
              />
              <path
                v-else-if="opening.kind === 'door'"
                :d="`M ${openingGeometry(opening).second.join(' ')} A ${opening.width} ${opening.width} 0 0 ${openingGeometry(opening).sweep} ${openingGeometry(opening).leaf.join(' ')} M ${openingGeometry(opening).first.join(' ')} L ${openingGeometry(opening).leaf.join(' ')}`"
                class="semantic-door"
              />
            </template>
          </g>

          <g v-show="layerVisibility.templates" class="semantic-instances">
            <use
              v-for="instance in level.instances"
              :key="instance.id"
              :href="`#semantic-template-${instance.templateId}`"
              :transform="`translate(${instance.position.join(' ')}) rotate(${instance.rotation ?? 0}) scale(${(instance.scale ?? [1, 1]).join(' ')}) translate(${templates.get(instance.templateId)!.anchor.map((value) => -value).join(' ')})`"
            />
          </g>

          <g v-show="layerVisibility.labels" class="semantic-labels">
            <g
              v-for="space in level.spaces.filter((item) => item.labelStyle !== 'hidden')"
              :key="space.id"
              :transform="`translate(${space.labelPosition.join(' ')}) scale(${labelScale})`"
              :class="[
                space.kind === 'excluded' ? 'semantic-area-tag' : 'semantic-room-tag',
                { 'semantic-room-tag--selected': selectedSpace?.id === space.id },
              ]"
            >
              <rect v-if="space.kind === 'excluded'" x="-450" y="-220" width="900" height="440" rx="130" />
              <text y="12">{{ space.number ?? space.name }}</text>
            </g>
          </g>

          <g v-if="mode === 'edit'" class="boundary-edit-layer">
            <template v-if="selectedSpace">
              <path :d="pathD(selectedSpace.boundary, true)" class="boundary-edit-outline" />
              <line
                v-for="(point, index) in selectedSpace.boundary"
                :key="`edge-${index}`"
                :x1="point[0]" :y1="point[1]"
                :x2="selectedSpace.boundary[(index + 1) % selectedSpace.boundary.length][0]"
                :y2="selectedSpace.boundary[(index + 1) % selectedSpace.boundary.length][1]"
                class="boundary-edit-edge-hit"
                @dblclick.stop="insertVertexOnEdge($event, index)"
              />
              <circle
                v-for="(point, index) in selectedSpace.boundary"
                :key="`vertex-${index}`"
                :cx="point[0]" :cy="point[1]" :r="120 * labelScale"
                :class="['boundary-edit-handle', { active: activeVertex === index }]"
                @pointerdown="startVertexDrag($event, index)"
              />
            </template>
            <template v-if="draftBoundary.length">
              <path :d="pathD(draftBoundary, false)" class="boundary-edit-draft" />
              <circle v-for="(point, index) in draftBoundary" :key="`draft-${index}`" :cx="point[0]" :cy="point[1]" :r="95 * labelScale" class="boundary-edit-draft-point" />
            </template>
          </g>

          <g v-if="measurementPoints.length" class="measurement-layer">
            <path :d="measurementPath" :class="{ 'measurement-fill': mode === 'area' && measurementPoints.length > 2 }" />
            <circle v-for="(point, index) in measurementPoints" :key="index" :cx="point[0]" :cy="point[1]" :r="130 * labelScale" />
          </g>
        </svg>

        <nav class="tool-rail" aria-label="图纸工具">
          <button :class="{ active: mode === 'pan' }" type="button" @click="setMode('pan')"><IconGlyph name="hand" /><span>平移</span></button>
          <button :class="{ active: mode === 'distance' }" type="button" @click="setMode('distance')"><IconGlyph name="ruler" /><span>距离</span></button>
          <button :class="{ active: mode === 'area' }" type="button" @click="setMode('area')"><IconGlyph name="area" /><span>面积</span></button>
          <button :class="{ active: mode === 'edit' }" type="button" @click="setMode('edit')"><IconGlyph name="edit" /><span>编辑房区</span></button>
          <div class="tool-divider"></div>
          <button type="button" @click="layerMenuOpen = !layerMenuOpen"><IconGlyph name="layers" /><span>图层</span></button>
        </nav>

        <div v-if="layerMenuOpen" class="layer-popover semantic-layer-popover">
          <div class="layer-popover__header"><strong>语义图层</strong><button type="button" @click="layerMenuOpen = false">完成</button></div>
          <label><input v-model="layerVisibility.structure" type="checkbox" /><span class="layer-swatch"></span><span>建筑结构</span><small>{{ (level.details?.length ?? 0) + level.walls.length }}</small></label>
          <label><input v-model="layerVisibility.templates" type="checkbox" /><span class="layer-swatch layer-swatch--fixtures"></span><span>家具设备</span><small>{{ level.instances.length }}</small></label>
          <label><input v-model="layerVisibility.labels" type="checkbox" /><span class="layer-swatch layer-swatch--annotations"></span><span>空间标签</span><small>{{ level.spaces.length }}</small></label>
          <label><input v-model="layerVisibility.zones" type="checkbox" /><span class="layer-swatch layer-swatch--dimensions"></span><span>区域标记</span><small>{{ excludedSpaces.length }}</small></label>
        </div>

        <BoundaryEditorPanel
          v-if="mode === 'edit'"
          :spaces="level.spaces"
          :selected-id="selectedSpaceId"
          :active-vertex="activeVertex"
          :dirty="editDirty"
          :issues="editIssues"
          :can-undo="editPast.length > 0"
          :can-redo="editFuture.length > 0"
          :creating="Boolean(creatingSpace)"
          :draft-point-count="draftBoundary.length"
          :saving="saving"
          :save-message="saveMessage"
          @close="setMode('pan')"
          @select="selectSpaceById"
          @undo="undoEdit"
          @redo="redoEdit"
          @add-vertex="addVertex"
          @delete-vertex="deleteVertex"
          @begin-create="beginCreateSpace"
          @finish-create="finishCreateSpace"
          @cancel-create="cancelCreateSpace"
          @save="saveEdits"
        />

        <div class="zoom-controls">
          <button type="button" aria-label="放大" @click="zoomAt(0.82)"><IconGlyph name="plus" /></button>
          <button type="button" aria-label="缩小" @click="zoomAt(1.18)"><IconGlyph name="minus" /></button>
          <button type="button" aria-label="适合窗口" @click="fitDrawing"><IconGlyph name="fit" /></button>
        </div>

        <div v-if="mode !== 'pan'" class="measurement-status">
          <div><p class="eyebrow">{{ mode === 'distance' ? '两点距离' : '多点面积' }}</p><strong v-if="distanceResult != null">{{ formatDistance(distanceResult) }}</strong><strong v-else-if="areaResult != null">{{ formatArea(areaResult) }}</strong><span v-else>{{ mode === 'distance' ? '在图上选择两个点' : '依次选择边界点' }}</span></div>
          <button type="button" @click="measurementPoints = []">清除</button>
        </div>

        <div class="scale-readout"><span>单位</span><strong>mm</strong><i></i><span>JSON v{{ workingData.schemaVersion }}</span></div>
      </div>
    </section>

    <SemanticInfoPanel :data="workingData" :selected="selectedSpace" :open="panelOpen" @close="panelOpen = false" @select="selectSpace" />
    <div v-if="panelOpen" class="panel-scrim" @click="panelOpen = false"></div>
  </div>
</template>
