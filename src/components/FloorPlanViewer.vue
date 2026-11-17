<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import { cadToLocal, clampViewBox, distanceMm, formatArea, formatDistance, localToCad, pointsToPath, polygonAreaM2, wheelZoomFactor } from '../geometry'
import type { FloorplanData, FloorplanSpace, LocalViewBox, Point, ToolMode } from '../types'
import IconGlyph from './IconGlyph.vue'
import InfoPanel from './InfoPanel.vue'

const props = defineProps<{ data: FloorplanData }>()

const drawingWidth = props.data.viewport.maxX - props.data.viewport.minX
const drawingHeight = props.data.viewport.maxY - props.data.viewport.minY
const svgRef = ref<SVGSVGElement>()
const viewBox = ref<LocalViewBox>({ x: 0, y: 0, width: drawingWidth, height: drawingHeight })
const mode = ref<ToolMode>('pan')
const selectedSpace = ref<FloorplanSpace>()
const measurementPoints = ref<Point[]>([])
const layerMenuOpen = ref(false)
const panelOpen = ref(false)
const didDrag = ref(false)
const pointers = new Map<number, { x: number; y: number }>()
let previousPinchDistance = 0

const visibleLayers = reactive<Record<string, boolean>>(
  Object.fromEntries(props.data.layers.map((layer) => [layer.id, layer.defaultVisible])),
)

const drawingPaths = computed(() => {
  const byLayer: Record<string, string[]> = {}
  for (const entity of props.data.entities) {
    if (entity.kind !== 'path') continue
    ;(byLayer[entity.layerId] ??= []).push(pointsToPath(entity.points, props.data.viewport, entity.closed))
  }
  return Object.fromEntries(Object.entries(byLayer).map(([layer, values]) => [layer, values.join('')]))
})

const drawingTexts = computed(() => props.data.entities.filter((entity) => entity.kind === 'text'))
const svgViewBox = computed(() => `${viewBox.value.x} ${viewBox.value.y} ${viewBox.value.width} ${viewBox.value.height}`)
const measurementLocalPoints = computed(() => measurementPoints.value.map((point) => cadToLocal(point, props.data.viewport)))
const measurementPath = computed(() => pointsToPath(measurementPoints.value, props.data.viewport, mode.value === 'area' && measurementPoints.value.length > 2))
const distanceResult = computed(() => measurementPoints.value.length === 2 ? distanceMm(measurementPoints.value[0], measurementPoints.value[1]) : null)
const areaResult = computed(() => measurementPoints.value.length > 2 ? polygonAreaM2(measurementPoints.value) : null)

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
  viewBox.value = clampViewBox({
    x: localX - width * xRatio,
    y: localY - height * yRatio,
    width,
    height,
  }, drawingWidth, drawingHeight)
}

function eventToLocal(event: { clientX: number; clientY: number }): Point {
  const svg = svgRef.value!
  const matrix = svg.getScreenCTM()
  if (matrix) {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse())
    return [point.x, point.y]
  }
  const rect = svg.getBoundingClientRect()
  return [
    viewBox.value.x + ((event.clientX - rect.left) / rect.width) * viewBox.value.width,
    viewBox.value.y + ((event.clientY - rect.top) / rect.height) * viewBox.value.height,
  ]
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
      const midpoint = { clientX: (values[0].x + values[1].x) / 2, clientY: (values[0].y + values[1].y) / 2 }
      const [x, y] = eventToLocal(midpoint)
      zoomAt(Math.pow(previousPinchDistance / distance, 0.55), x, y)
      didDrag.value = true
    }
    previousPinchDistance = distance
    return
  }

  if (mode.value !== 'pan') return
  const [previousX, previousY] = eventToLocal({ clientX: previous.x, clientY: previous.y })
  const [currentX, currentY] = eventToLocal({ clientX: current.x, clientY: current.y })
  const dx = currentX - previousX
  const dy = currentY - previousY
  if (Math.abs(current.x - previous.x) + Math.abs(current.y - previous.y) > 1) didDrag.value = true
  viewBox.value = clampViewBox({
    ...viewBox.value,
    x: viewBox.value.x - dx,
    y: viewBox.value.y - dy,
  }, drawingWidth, drawingHeight)
}

function onPointerUp(event: PointerEvent) {
  pointers.delete(event.pointerId)
  if (pointers.size < 2) previousPinchDistance = 0
}

function onCanvasClick(event: MouseEvent) {
  if (didDrag.value || mode.value === 'pan') return
  const cadPoint = localToCad(eventToLocal(event), props.data.viewport)
  if (mode.value === 'distance') {
    measurementPoints.value = measurementPoints.value.length >= 2 ? [cadPoint] : [...measurementPoints.value, cadPoint]
  } else {
    measurementPoints.value = [...measurementPoints.value, cadPoint]
  }
}

function selectSpace(space: FloorplanSpace) {
  selectedSpace.value = space
  panelOpen.value = true
  const [x, y] = cadToLocal(space.labelPosition, props.data.viewport)
  const width = Math.min(viewBox.value.width, drawingWidth / 3.2)
  const height = width * (drawingHeight / drawingWidth)
  viewBox.value = clampViewBox({ x: x - width / 2, y: y - height / 2, width, height }, drawingWidth, drawingHeight)
  nextTick(() => svgRef.value?.focus())
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
  <div class="viewer-shell">
    <section class="drawing-stage" :class="`mode-${mode}`">
      <header class="viewer-header">
        <div class="brand-lockup">
          <span class="brand-mark">FP</span>
          <div>
            <strong>Floorplan</strong>
            <span>JSON / CAD Viewer</span>
          </div>
        </div>
        <div class="header-project">
          <span>{{ data.project.sourceDrawing }}</span>
          <strong>{{ data.project.name }}</strong>
        </div>
        <button class="mobile-info-button" type="button" @click="panelOpen = true">项目 / 房间</button>
      </header>

      <div class="canvas-wrap">
        <svg
          ref="svgRef"
          class="floorplan-svg"
          :viewBox="svgViewBox"
          role="img"
          :aria-label="`${data.project.name}${data.project.sourceDrawing}`"
          tabindex="0"
          @wheel="onWheel"
          @pointerdown="onPointerDown"
          @pointermove="onPointerMove"
          @pointerup="onPointerUp"
          @pointercancel="onPointerUp"
          @click="onCanvasClick"
        >
          <rect x="0" y="0" :width="drawingWidth" :height="drawingHeight" class="drawing-paper" />

          <path
            v-for="layer in data.layers"
            v-show="visibleLayers[layer.id] && drawingPaths[layer.id]"
            :key="layer.id"
            :d="drawingPaths[layer.id]"
            :class="['cad-path', `cad-path--${layer.id}`]"
          />

          <g v-show="visibleLayers.annotations" class="cad-text-layer">
            <text
              v-for="entity in drawingTexts"
              v-show="visibleLayers[entity.layerId]"
              :key="entity.id"
              :x="cadToLocal(entity.position, data.viewport)[0]"
              :y="cadToLocal(entity.position, data.viewport)[1]"
              :font-size="entity.height"
              :transform="`rotate(${-entity.rotation} ${cadToLocal(entity.position, data.viewport).join(' ')})`"
            >{{ entity.content }}</text>
          </g>

          <g class="spaces-layer">
            <path
              v-for="space in data.spaces"
              :key="space.id"
              :d="pointsToPath(space.selectionBoundary, data.viewport, true)"
              :class="['space-hit', { 'space-hit--selected': selectedSpace?.id === space.id }]"
              tabindex="0"
              role="button"
              :aria-label="`${space.label}号房`"
              @click.stop="selectSpace(space)"
              @keydown.enter.stop="selectSpace(space)"
            />
            <g v-if="selectedSpace" class="selected-marker" :transform="`translate(${cadToLocal(selectedSpace.labelPosition, data.viewport).join(' ')})`">
              <circle r="360" />
              <text y="105">{{ selectedSpace.label }}</text>
            </g>
          </g>

          <g v-if="measurementPoints.length" class="measurement-layer">
            <path :d="measurementPath" :class="{ 'measurement-fill': mode === 'area' && measurementPoints.length > 2 }" />
            <circle v-for="(point, index) in measurementLocalPoints" :key="index" :cx="point[0]" :cy="point[1]" r="145" />
          </g>
        </svg>

        <nav class="tool-rail" aria-label="图纸工具">
          <button :class="{ active: mode === 'pan' }" type="button" aria-label="平移" @click="setMode('pan')"><IconGlyph name="hand" /><span>平移</span></button>
          <button :class="{ active: mode === 'distance' }" type="button" aria-label="测量距离" @click="setMode('distance')"><IconGlyph name="ruler" /><span>距离</span></button>
          <button :class="{ active: mode === 'area' }" type="button" aria-label="测量面积" @click="setMode('area')"><IconGlyph name="area" /><span>面积</span></button>
          <div class="tool-divider"></div>
          <button type="button" aria-label="图层" @click="layerMenuOpen = !layerMenuOpen"><IconGlyph name="layers" /><span>图层</span></button>
        </nav>

        <div v-if="layerMenuOpen" class="layer-popover">
          <div class="layer-popover__header"><strong>图层显示</strong><button type="button" @click="layerMenuOpen = false">完成</button></div>
          <label v-for="layer in data.layers" :key="layer.id">
            <input v-model="visibleLayers[layer.id]" type="checkbox" />
            <span class="layer-swatch" :class="`layer-swatch--${layer.id}`"></span>
            <span>{{ layer.name }}</span>
            <small>{{ layer.entityCount.toLocaleString() }}</small>
          </label>
        </div>

        <div class="zoom-controls">
          <button type="button" aria-label="放大" @click="zoomAt(0.82)"><IconGlyph name="plus" /></button>
          <button type="button" aria-label="缩小" @click="zoomAt(1.18)"><IconGlyph name="minus" /></button>
          <button type="button" aria-label="适合窗口" @click="fitDrawing"><IconGlyph name="fit" /></button>
        </div>

        <div v-if="mode !== 'pan'" class="measurement-status">
          <div>
            <p class="eyebrow">{{ mode === 'distance' ? '两点距离' : '多点面积' }}</p>
            <strong v-if="distanceResult != null">{{ formatDistance(distanceResult) }}</strong>
            <strong v-else-if="areaResult != null">{{ formatArea(areaResult) }}</strong>
            <span v-else>{{ mode === 'distance' ? '在图上选择两个点' : '依次选择边界点' }}</span>
          </div>
          <button type="button" @click="measurementPoints = []">清除</button>
        </div>

        <div class="scale-readout">
          <span>单位</span><strong>mm</strong><i></i><span>JSON v{{ data.schemaVersion }}</span>
        </div>
      </div>
    </section>

    <InfoPanel
      :data="data"
      :selected="selectedSpace"
      :open="panelOpen"
      @close="panelOpen = false"
      @select="selectSpace"
    />
    <div v-if="panelOpen" class="panel-scrim" @click="panelOpen = false"></div>
  </div>
</template>
