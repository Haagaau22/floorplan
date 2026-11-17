<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SemanticFloorplanData, SemanticSpace } from '../types'
import IconGlyph from './IconGlyph.vue'

const props = defineProps<{
  data: SemanticFloorplanData
  selected?: SemanticSpace
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  select: [space: SemanticSpace]
}>()

const query = ref('')
const level = computed(() => props.data.levels[0])
const selectableSpaces = computed(() => level.value.spaces.filter((space) => space.kind !== 'excluded' && space.labelStyle !== 'hidden'))
const filteredSpaces = computed(() => {
  const value = query.value.trim().toLowerCase()
  if (!value) return selectableSpaces.value
  return selectableSpaces.value.filter((space) => `${space.number ?? ''} ${space.name}`.toLowerCase().includes(value))
})
const instanceCount = computed(() => level.value.instances.length)
const excludedCount = computed(() => level.value.spaces.filter((space) => space.kind === 'excluded').length)
</script>

<template>
  <aside class="info-panel semantic-panel" :class="{ 'info-panel--open': open }" aria-label="项目信息">
    <button class="panel-close icon-button" type="button" aria-label="关闭信息面板" @click="emit('close')">
      <IconGlyph name="close" />
    </button>

    <div class="project-summary">
      <p class="eyebrow">Project / {{ data.project.id }}</p>
      <div class="project-summary__title">
        <h1>{{ data.project.name }}</h1>
        <span class="status-dot" :title="data.project.status"></span>
      </div>
      <p>语义 JSON 是唯一数据源 · {{ level.name }}</p>
      <div class="summary-stats">
        <div><strong>{{ selectableSpaces.length }}</strong><span>空间</span></div>
        <div><strong>{{ data.templates.length }}</strong><span>模板</span></div>
        <div><strong>{{ instanceCount }}</strong><span>实例</span></div>
      </div>
    </div>

    <section v-if="selected" class="selected-room" aria-live="polite">
      <div class="selected-room__number">{{ selected.number ?? '·' }}</div>
      <div class="selected-room__title">
        <div>
          <p class="eyebrow">当前空间 / {{ selected.kind }}</p>
          <h2>{{ selected.name }}</h2>
        </div>
        <span class="review-chip">{{ selected.boundaryStatus === 'verified' ? '已确认' : '边界待复核' }}</span>
      </div>
      <dl class="metric-grid">
        <div><dt>标识</dt><dd>{{ selected.number ?? '—' }}</dd></div>
        <div><dt>空间类型</dt><dd>{{ selected.kind }}</dd></div>
        <div><dt>边界点</dt><dd>{{ selected.boundary.length }}</dd></div>
        <div><dt>坐标单位</dt><dd>mm</dd></div>
      </dl>
      <p class="verification-note">房间标签采用固定屏幕尺寸；放大图纸时不会变得过大或挡住结构。</p>
    </section>

    <section class="room-list semantic-space-list">
      <div class="section-heading">
        <div><p class="eyebrow">Spaces</p><h2>空间导航</h2></div>
        <span class="count-badge">{{ filteredSpaces.length }}</span>
      </div>
      <label class="search-field">
        <IconGlyph name="search" />
        <input v-model="query" type="search" placeholder="搜索房号或空间" />
      </label>
      <div class="semantic-space-list__items">
        <button
          v-for="space in filteredSpaces"
          :key="space.id"
          type="button"
          :class="{ selected: selected?.id === space.id }"
          @click="emit('select', space)"
        >
          <strong>{{ space.number ?? '—' }}</strong>
          <span>{{ space.name }}</span>
          <small>{{ space.boundaryStatus === 'verified' ? '已确认' : '待复核' }}</small>
        </button>
      </div>
      <p v-if="excludedCount" class="semantic-panel__note">图中 {{ excludedCount }} 处非项目区域以斜线阴影标识。</p>
    </section>
  </aside>
</template>
