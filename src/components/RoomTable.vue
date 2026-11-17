<script setup lang="ts">
import {
  columnFilteringFeature,
  createColumnHelper,
  createFilteredRowModel,
  createSortedRowModel,
  filterFn_includesString,
  FlexRender,
  rowSortingFeature,
  sortFn_basic,
  sortFn_text,
  tableFeatures,
  useTable,
} from '@tanstack/vue-table'
import { computed, ref, watch } from 'vue'
import IconGlyph from './IconGlyph.vue'
import type { FloorplanSpace } from '../types'

const props = defineProps<{
  spaces: FloorplanSpace[]
  selectedId?: string
}>()

const emit = defineEmits<{
  select: [space: FloorplanSpace]
}>()

const filter = ref('')
const features = tableFeatures({
  columnFilteringFeature,
  rowSortingFeature,
  filteredRowModel: createFilteredRowModel(),
  sortedRowModel: createSortedRowModel(),
  filterFns: { includesString: filterFn_includesString },
  sortFns: { basic: sortFn_basic, text: sortFn_text },
})
const columnHelper = createColumnHelper<typeof features, FloorplanSpace>()
const columns = columnHelper.columns([
  columnHelper.accessor('label', {
    header: '房号',
    filterFn: 'includesString',
    sortFn: (rowA, rowB) => Number(rowA.original.label) - Number(rowB.original.label),
  }),
  columnHelper.accessor((row) => row.metrics.areaM2, {
    id: 'area',
    header: '面积',
    cell: (info) => info.getValue() == null ? '待复核' : `${info.getValue()!.toFixed(2)} ㎡`,
  }),
  columnHelper.accessor((row) => row.business.floorTile, {
    id: 'tile',
    header: '地砖',
    cell: (info) => info.getValue() ?? '—',
  }),
])

const data = computed(() => props.spaces)
const table = useTable({
  features,
  data,
  columns,
  initialState: { sorting: [{ id: 'label', desc: false }] },
})

watch(filter, (value) => table.getColumn('label')?.setFilterValue(value.trim()))
</script>

<template>
  <section class="room-list" aria-labelledby="room-list-title">
    <div class="section-heading">
      <div>
        <p class="eyebrow">空间索引</p>
        <h2 id="room-list-title">32 套房间</h2>
      </div>
      <span class="count-badge">{{ table.getFilteredRowModel().rows.length }}</span>
    </div>

    <label class="search-field">
      <IconGlyph name="search" />
      <span class="sr-only">按房号查询</span>
      <input v-model="filter" inputmode="numeric" type="search" placeholder="输入房号" />
    </label>

    <div class="room-table-wrap">
      <table class="room-table">
        <thead>
          <tr v-for="headerGroup in table.getHeaderGroups()" :key="headerGroup.id">
            <th
              v-for="header in headerGroup.headers"
              :key="header.id"
              :class="{ sortable: header.column.getCanSort() }"
              @click="header.column.getToggleSortingHandler()?.($event)"
            >
              <FlexRender :header="header" />
              <span v-if="header.column.getIsSorted() === 'asc'">↑</span>
              <span v-else-if="header.column.getIsSorted() === 'desc'">↓</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in table.getRowModel().rows"
            :key="row.id"
            :class="{ selected: row.original.id === selectedId }"
            tabindex="0"
            @click="emit('select', row.original)"
            @keydown.enter="emit('select', row.original)"
          >
            <td v-for="cell in row.getAllCells()" :key="cell.id">
              <FlexRender :cell="cell" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
