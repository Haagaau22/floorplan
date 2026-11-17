import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SemanticFloorplanData } from '../types'
import SemanticFloorPlanViewer from './SemanticFloorPlanViewer.vue'

const saveFloorplanMock = vi.fn().mockResolvedValue({ uploadedAt: '2026-11-18T00:00:00Z' })

vi.mock('../api', () => ({
  saveFloorplan: (...args: unknown[]) => saveFloorplanMock(...args),
}))

function fixture(): SemanticFloorplanData {
  return {
    schemaVersion: '2.0.0',
    project: { id: 'apartment', name: 'Test plan', status: 'review' },
    coordinateSystem: { units: 'mm', xAxis: 'right', yAxis: 'down' },
    canvas: { width: 5_000, height: 4_000 },
    templates: [],
    levels: [{
      id: 'level-01',
      name: 'Level',
      walls: [],
      openings: [],
      instances: [],
      details: [],
      spaces: [{
        id: 'room-1',
        kind: 'apartment',
        name: '1号房',
        number: '1',
        boundary: [[500, 500], [3_500, 500], [3_500, 3_000], [500, 3_000]],
        labelPosition: [2_000, 1_750],
        labelStyle: 'room-tag',
        boundaryStatus: 'verified',
      }],
    }],
  }
}

describe('SemanticFloorPlanViewer boundary editing', () => {
  beforeEach(() => {
    saveFloorplanMock.mockClear()
  })

  it('edits, undoes, and saves a room boundary', async () => {
    const wrapper = mount(SemanticFloorPlanViewer, { props: { data: fixture() } })
    const editButton = wrapper.findAll('button').find((button) => button.text().includes('编辑房区'))!
    await editButton.trigger('click')
    await wrapper.find('.space-hit').trigger('click')
    expect(wrapper.findAll('.boundary-edit-handle')).toHaveLength(4)

    const addButton = wrapper.findAll('.boundary-editor button').find((button) => button.text() === '增加节点')!
    await addButton.trigger('click')
    expect(wrapper.findAll('.boundary-edit-handle')).toHaveLength(5)

    const undoButton = wrapper.findAll('.boundary-editor button').find((button) => button.text() === '撤销')!
    await undoButton.trigger('click')
    expect(wrapper.findAll('.boundary-edit-handle')).toHaveLength(4)

    const redoButton = wrapper.findAll('.boundary-editor button').find((button) => button.text() === '重做')!
    await redoButton.trigger('click')
    expect(wrapper.findAll('.boundary-edit-handle')).toHaveLength(5)

    const saveButton = wrapper.findAll('.boundary-editor button').find((button) => button.text() === '保存到服务器')!
    expect(saveButton.attributes('disabled')).toBeUndefined()
    await saveButton.trigger('click')
    await flushPromises()

    expect(saveFloorplanMock).toHaveBeenCalledOnce()
    expect(saveFloorplanMock.mock.calls[0][0].levels[0].spaces[0].boundary).toHaveLength(5)
    expect(saveFloorplanMock.mock.calls[0]).toHaveLength(1)
    expect(wrapper.text()).toContain('已保存')
  })
})
