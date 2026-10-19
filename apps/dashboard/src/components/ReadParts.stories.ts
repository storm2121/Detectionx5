import type { Meta, StoryObj } from '@storybook/vue3'

import type { ReadOut } from '@/api/types'
import accepted from '@/fixtures/read-accepted.json'
import queued from '@/fixtures/read-queued.json'

import CharacterHeatmap from './CharacterHeatmap.vue'
import ConfidenceMeter from './ConfidenceMeter.vue'
import ConformalSet from './ConformalSet.vue'
import FusionTable from './FusionTable.vue'
import PhotoFrame from './PhotoFrame.vue'
import PlateFields from './PlateFields.vue'
import ViewCard from './ViewCard.vue'

// Synthetic reads captured from the service on the parity scenes; every number in them is
// synthetic, not real-world accuracy.
const ACCEPTED = accepted as unknown as ReadOut
const QUEUED = queued as unknown as ReadOut

const meta: Meta = { title: 'Read/Parts' }
export default meta
type Story = StoryObj

export const StandardPlate: Story = {
  render: () => ({
    components: { PlateFields },
    setup: () => ({ read: ACCEPTED }),
    template: '<PlateFields :fields="read.fields" :format="read.format" :plate="read.plate" />',
  }),
}

export const TemporaryPlate: Story = {
  render: () => ({
    components: { PlateFields },
    template:
      '<PlateFields :fields="{ digits: \'72173\', letter: null, region: null }" format="temporary" plate="72173 WW" />',
  }),
}

export const NoPlate: Story = {
  render: () => ({
    components: { PlateFields },
    template: '<PlateFields :fields="null" :format="null" :plate="null" />',
  }),
}

export const Confidence: Story = {
  render: () => ({
    components: { ConfidenceMeter },
    template: `<div style="display: grid; gap: 24px; max-width: 420px">
      <ConfidenceMeter :value="0.99999997" :threshold="0.9" label="Calibrated confidence" />
      <ConfidenceMeter :value="0.167" :threshold="0.9" label="Calibrated confidence" />
      <ConfidenceMeter :value="0.62" :threshold="null" :calibrated="false" label="Vote share" />
    </div>`,
  }),
}

export const ConformalSets: Story = {
  render: () => ({
    components: { ConformalSet },
    template: `<div style="display: grid; gap: 24px; max-width: 480px">
      <ConformalSet :set="['27-د-9']" :level="0.95" prediction="27-د-9" />
      <ConformalSet :set="['27-د-9', '22-د-9', '227-د-9']" :level="0.9" prediction="27-د-9" />
      <ConformalSet :set="[]" :level="0.95" prediction="54-ب-4" />
      <ConformalSet :set="null" :level="null" prediction="54-ب-4" />
    </div>`,
  }),
}

export const Fusion: Story = {
  render: () => ({
    components: { FusionTable },
    setup: () => ({ read: ACCEPTED }),
    template: '<FusionTable :read="read" />',
  }),
}

export const HeatmapConfident: Story = {
  render: () => ({
    components: { CharacterHeatmap },
    setup: () => ({ read: ACCEPTED }),
    template: '<CharacterHeatmap :positions="read.positions" />',
  }),
}

export const HeatmapUncertain: Story = {
  render: () => ({
    components: { CharacterHeatmap },
    setup: () => ({ read: QUEUED }),
    template: '<CharacterHeatmap :positions="read.positions" :minimum="0.002" />',
  }),
}

export const Views: Story = {
  render: () => ({
    components: { ViewCard },
    setup: () => ({ read: ACCEPTED }),
    template: `<div class="dx-grid-3">
      <ViewCard v-for="view in read.views" :key="view.index" :view="view" />
    </div>`,
  }),
}

export const PhotoWithBox: Story = {
  render: () => ({
    components: { PhotoFrame },
    setup: () => ({ read: ACCEPTED }),
    template: `<div style="max-width: 420px">
      <PhotoFrame src="/runtime/parity/scene_02.png" alt="Synthetic street photo (a parity fixture)" :box="read.views[2].box" badge="View 3" removable>
        scene_02.png
      </PhotoFrame>
    </div>`,
  }),
}
