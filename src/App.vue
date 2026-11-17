<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import FloorPlanViewer from './components/FloorPlanViewer.vue'
import SemanticFloorPlanViewer from './components/SemanticFloorPlanViewer.vue'
import { fetchFloorplan } from './api'
import { isSemanticFloorplan } from './types'

const query = useQuery({
  queryKey: ['floorplan', 'apartment'],
  queryFn: () => fetchFloorplan('apartment'),
})
</script>

<template>
  <main class="app-shell">
    <div v-if="query.isPending.value" class="load-state">
      <div class="load-state__mark">FP</div>
      <div>
        <p class="eyebrow">正在读取项目 JSON</p>
        <h1>生成语义户型图…</h1>
      </div>
    </div>

    <div v-else-if="query.isError.value" class="load-state load-state--error">
      <div class="load-state__mark">!</div>
      <div>
        <p class="eyebrow">数据不可用</p>
        <h1>无法打开户型</h1>
        <p>{{ query.error.value?.message }}</p>
        <button class="primary-button" type="button" @click="query.refetch()">重新加载</button>
      </div>
    </div>

    <SemanticFloorPlanViewer v-else-if="query.data.value && isSemanticFloorplan(query.data.value)" :data="query.data.value" />
    <FloorPlanViewer v-else-if="query.data.value" :data="query.data.value" />
  </main>
</template>
