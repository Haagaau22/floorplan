<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { clampViewBox, distanceMm, formatArea, formatDistance, polygonAreaM2, wheelZoomFactor } from '../geometry'
import type { LocalViewBox, Point, SemanticFloorplanData, SemanticOpening, SemanticSpace, ToolMode } from '../types'
import IconGlyph from './IconGlyph.vue'
import SemanticInfoPanel from './SemanticInfoPanel.vue'

const props = defineProps<{ data: SemanticFloorplanData }>()
const level = props.data.levels[0]
const drawingWidth = props.data.canvas.width
const drawingHeight = props.data.canvas.height
const svgRef = ref<SVGSVGElement>()
const viewBox = ref<LocalViewBox>({ x: 0, y: 0, width: drawingWidth, height: drawingHeight })
const mode = ref<ToolMode>('pan')
const selectedSpace = ref<SemanticSpace>()
const measurementPoints = ref<Point[]>([])
const layerMenuOpen = ref(false)
const panelOpen = ref(false)
const didDrag = ref(false)
const layerVisibility = ref({ structure: true, templates: true, labels: true, zones: true })
const pointers = new Map<number, { x: number; y: number }>()
let previousPinchDistance = 0

const templates = new Map(props.data.templates.map((template) => [template.id, template]))
const walls = new Map(level.walls.map((wall) => [wall.id, wall]))
const svgViewBox = computed(() => `${viewBox.value.x} ${viewBox.value.y} ${viewBox.value.width} ${viewBox.value.height}`)
const labelScale = computed(() => viewBox.value.width / 30_000)
const detailsPath = computed(() => (level.details ?? []).map((item) => pathD(item.points, item.closed)).join(' '))
const measurementPath = computed(() => pathD(measurementPoints.value, mode.value === 'area' && measurementPoints.value.length > 2))
const distanceResult = computed(() => measurementPoints.value.length === 2 ? distanceMm(measurementPoints.value[0], measurementPoints.value[1]) : null)
const areaResult = computed(() => measurementPoints.value.length > 2 ? polygonAreaM2(measurementPoints.value) : null)
const regularSpaces = computed(() => level.spaces.filter((space) => space.kind !== 'excluded'))
const excludedSpaces = computed(() => level.spaces.filter((space) => space.kind === 'excluded'))

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
  pointers.delete(event.pointerId)
  if (pointers.size < 2) previousPinchDistance = 0
}

function onCanvasClick(event: MouseEvent) {
  if (didDrag.value || mode.value === 'pan') return
  const point = eventToLocal(event)
  if (mode.value === 'distance') {
    measurementPoints.value = measurementPoints.value.length >= 2 ? [point] : [...measurementPoints.value, point]
  } else {
    measurementPoints.value = [...measurementPoints.value, point]
  }
}

function selectSpace(space: SemanticSpace) {
  selectedSpace.value = space
  panelOpen.value = true
  const width = Math.min(viewBox.value.width, drawingWidth / 3.2)
  const height = width * drawingHeight / drawingWidth
  viewBox.value = clampViewBox({ x: space.labelPosition[0] - width / 2, y: space.labelPosition[1] - height / 2, width, height }, drawingWidth, drawingHeight)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    measurementPoints.value = []
    selectedSpace.value = undefined
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
        <div class="header-project"><span>JSON v{{ data.schemaVersion }}</span><strong>{{ data.project.name }}</strong></div>
        <button class="mobile-info-button" type="button" @click="panelOpen = true">项目 / 空间</button>
      </header>

      <div class="canvas-wrap">
        <svg
          ref="svgRef"
          class="floorplan-svg semantic-svg"
          :viewBox="svgViewBox"
          role="img"
          :aria-label="data.project.name"
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

          <g class="semantic-space-hits">
            <path
              v-for="space in regularSpaces"
              :key="space.id"
              :d="pathD(space.boundary, true)"
              :class="['space-hit', { 'space-hit--selected': selectedSpace?.id === space.id }]"
              tabindex="0" role="button" :aria-label="space.name"
              @click.stop="selectSpace(space)" @keydown.enter.stop="selectSpace(space)"
            />
          </g>

          <g v-show="layerVisibility.labels" class="semantic-labels">
            <g
              v-for="space in level.spaces.filter((item) => item.labelStyle !== 'hidden')"
              :key="space.id"
              :transform="`translate(${space.labelPosition.join(' ')}) scale(${labelScale})`"
              :class="space.kind === 'excluded' ? 'semantic-area-tag' : 'semantic-room-tag'"
            >
              <rect x="-450" y="-220" width="900" height="440" rx="130" />
              <text y="12">{{ space.number ?? space.name }}</text>
            </g>
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

        <div class="zoom-controls">
          <button type="button" aria-label="放大" @click="zoomAt(0.82)"><IconGlyph name="plus" /></button>
          <button type="button" aria-label="缩小" @click="zoomAt(1.18)"><IconGlyph name="minus" /></button>
          <button type="button" aria-label="适合窗口" @click="fitDrawing"><IconGlyph name="fit" /></button>
        </div>

        <div v-if="mode !== 'pan'" class="measurement-status">
          <div><p class="eyebrow">{{ mode === 'distance' ? '两点距离' : '多点面积' }}</p><strong v-if="distanceResult != null">{{ formatDistance(distanceResult) }}</strong><strong v-else-if="areaResult != null">{{ formatArea(areaResult) }}</strong><span v-else>{{ mode === 'distance' ? '在图上选择两个点' : '依次选择边界点' }}</span></div>
          <button type="button" @click="measurementPoints = []">清除</button>
        </div>

        <div class="scale-readout"><span>单位</span><strong>mm</strong><i></i><span>JSON v{{ data.schemaVersion }}</span></div>
      </div>
    </section>

    <SemanticInfoPanel :data="data" :selected="selectedSpace" :open="panelOpen" @close="panelOpen = false" @select="selectSpace" />
    <div v-if="panelOpen" class="panel-scrim" @click="panelOpen = false"></div>
  </div>
</template>
