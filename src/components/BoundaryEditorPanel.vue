<script setup lang="ts">
import { ref } from 'vue'
import type { SemanticSpace } from '../types'

const props = defineProps<{
  spaces: SemanticSpace[]
  selectedId?: string
  activeVertex?: number
  dirty: boolean
  issues: string[]
  canUndo: boolean
  canRedo: boolean
  creating: boolean
  draftPointCount: number
  saving: boolean
  saveMessage?: string
}>()

const emit = defineEmits<{
  close: []
  select: [id: string]
  undo: []
  redo: []
  addVertex: []
  deleteVertex: []
  beginCreate: [name: string, kind: SemanticSpace['kind']]
  finishCreate: []
  cancelCreate: []
  save: []
}>()

const newSpaceName = ref('公共区域')
const newSpaceKind = ref<SemanticSpace['kind']>('utility')

function selectSpace(event: Event) {
  emit('select', (event.target as HTMLSelectElement).value)
}

function beginCreate() {
  emit('beginCreate', newSpaceName.value.trim() || '公共区域', newSpaceKind.value)
}

</script>

<template>
  <section class="boundary-editor" aria-label="编辑房区">
    <header class="boundary-editor__header">
      <div><p class="eyebrow">Boundary editor</p><strong>编辑房区</strong></div>
      <button type="button" @click="emit('close')">完成</button>
    </header>

    <template v-if="!creating">
      <label class="boundary-editor__field">
        <span>当前空间</span>
        <select :value="selectedId" @change="selectSpace">
          <option value="">请选择空间</option>
          <option v-for="space in spaces" :key="space.id" :value="space.id">{{ space.number ? `${space.number}号房` : space.name }}</option>
        </select>
      </label>

      <div class="boundary-editor__actions">
        <button type="button" :disabled="!canUndo" @click="emit('undo')">撤销</button>
        <button type="button" :disabled="!canRedo" @click="emit('redo')">重做</button>
        <button type="button" :disabled="!selectedId" @click="emit('addVertex')">增加节点</button>
        <button type="button" :disabled="activeVertex == null" @click="emit('deleteVertex')">删除节点</button>
      </div>

      <p class="boundary-editor__hint">拖动橙色节点调整边界；双击边线可直接插入节点。节点会吸附到相邻房区边线。</p>

      <div class="boundary-editor__create">
        <strong>新增公共分区</strong>
        <div>
          <input v-model="newSpaceName" type="text" aria-label="新分区名称" />
          <select v-model="newSpaceKind" aria-label="新分区类型">
            <option value="utility">设备/水电</option>
            <option value="common">公共区域</option>
            <option value="excluded">排除区域</option>
            <option value="room">其他房间</option>
          </select>
          <button type="button" @click="beginCreate">开始绘制</button>
        </div>
      </div>
    </template>

    <div v-else class="boundary-editor__drawing">
      <strong>在图上依次点击边界点</strong>
      <span>已选择 {{ draftPointCount }} 个点</span>
      <div>
        <button type="button" :disabled="draftPointCount < 3" @click="emit('finishCreate')">闭合分区</button>
        <button type="button" @click="emit('cancelCreate')">取消</button>
      </div>
    </div>

    <div v-if="issues.length" class="boundary-editor__issues" role="alert">
      <strong>保存前需要处理</strong>
      <ul><li v-for="issue in issues" :key="issue">{{ issue }}</li></ul>
    </div>

    <footer class="boundary-editor__save">
      <span class="boundary-editor__open-warning">功能验证阶段：保存暂不需要登录</span>
      <button type="button" :disabled="!dirty || issues.length > 0 || saving" @click="emit('save')">
        {{ saving ? '保存中…' : '保存到服务器' }}
      </button>
      <small v-if="saveMessage">{{ saveMessage }}</small>
      <small v-else>{{ dirty ? '存在尚未保存的修改' : '当前数据已同步' }}</small>
    </footer>
  </section>
</template>
