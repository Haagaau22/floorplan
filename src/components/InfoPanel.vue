<script setup lang="ts">
import RoomTable from './RoomTable.vue'
import IconGlyph from './IconGlyph.vue'
import type { FloorplanData, FloorplanSpace } from '../types'

defineProps<{
  data: FloorplanData
  selected?: FloorplanSpace
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  select: [space: FloorplanSpace]
}>()
</script>

<template>
  <aside class="info-panel" :class="{ 'info-panel--open': open }" aria-label="项目信息">
    <button class="panel-close icon-button" type="button" aria-label="关闭信息面板" @click="emit('close')">
      <IconGlyph name="close" />
    </button>

    <div class="project-summary">
      <p class="eyebrow">Project / {{ data.project.id }}</p>
      <div class="project-summary__title">
        <h1>{{ data.project.name }}</h1>
        <span class="status-dot" title="工作基线"></span>
      </div>
      <p>{{ data.project.sourceDrawing }} · CAD 毫米坐标</p>
      <div class="summary-stats">
        <div><strong>{{ data.statistics.spaceCount }}</strong><span>套房</span></div>
        <div><strong>{{ data.statistics.pathCount.toLocaleString() }}</strong><span>路径</span></div>
        <div><strong>{{ data.dimensions.length }}</strong><span>尺寸</span></div>
      </div>
    </div>

    <section v-if="selected" class="selected-room" aria-live="polite">
      <div class="selected-room__number">{{ selected.label }}</div>
      <div class="selected-room__title">
        <div>
          <p class="eyebrow">当前空间</p>
          <h2>{{ selected.label }} 号房</h2>
        </div>
        <span class="review-chip">待复核</span>
      </div>

      <dl class="metric-grid">
        <div>
          <dt>套内地面</dt>
          <dd>{{ selected.metrics.areaM2 == null ? '—' : `${selected.metrics.areaM2.toFixed(2)} ㎡` }}</dd>
        </div>
        <div>
          <dt>空间周长</dt>
          <dd>{{ selected.metrics.perimeterM == null ? '待复核' : `${selected.metrics.perimeterM.toFixed(2)} m` }}</dd>
        </div>
        <div>
          <dt>卫生间</dt>
          <dd>{{ selected.business.bathroomAreaM2 == null ? '—' : `${Number(selected.business.bathroomAreaM2).toFixed(2)} ㎡` }}</dd>
        </div>
        <div>
          <dt>卫生间周长</dt>
          <dd>{{ selected.business.bathroomPerimeterM == null ? '—' : `${Number(selected.business.bathroomPerimeterM).toFixed(1)} m` }}</dd>
        </div>
      </dl>

      <div class="tile-spec">
        <div>
          <span>地面砖</span>
          <strong>{{ selected.business.floorTile ?? '—' }}</strong>
        </div>
        <div>
          <span>墙面砖</span>
          <strong>{{ selected.business.wallTile ?? '—' }}</strong>
        </div>
        <div v-if="selected.business.closedKitchen" class="tile-spec__wide">
          <span>封闭厨房</span>
          <strong>{{ Number(selected.business.closedKitchenAreaM2 ?? 0).toFixed(2) }} ㎡</strong>
        </div>
      </div>

      <p class="verification-note">{{ selected.verification.note }}</p>
    </section>

    <RoomTable
      :spaces="data.spaces"
      :selected-id="selected?.id"
      @select="emit('select', $event)"
    />
  </aside>
</template>
