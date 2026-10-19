import type { Meta, StoryObj } from '@storybook/vue3'
import { ref } from 'vue'

import type { ReadOut } from '@/api/types'
import accepted from '@/fixtures/read-accepted.json'
import queued from '@/fixtures/read-queued.json'
import type { Photo } from '@/stores/read'

import ConfidenceBar from './ConfidenceBar.vue'
import FusionTable from './FusionTable.vue'
import ModeToggle from './ModeToggle.vue'
import PhotoThumb from './PhotoThumb.vue'
import PhotoTray from './PhotoTray.vue'
import PlateReadout from './PlateReadout.vue'
import PredictionSet from './PredictionSet.vue'
import ViewCard from './ViewCard.vue'

// Synthetic reads captured from the service on the parity scenes; every number in them is
// synthetic, not real-world accuracy.
const ACCEPTED = accepted as unknown as ReadOut
const QUEUED = queued as unknown as ReadOut

const meta: Meta = { title: 'Read' }
export default meta
type Story = StoryObj

function photo(index: number): Photo {
  const name = `scene_0${index}.png`
  return {
    id: `p${index}`,
    file: new File([], name, { type: 'image/png' }),
    url: `/runtime/parity/${name}`,
    width: null,
    height: null,
    view: index,
  }
}

export const PlateAndCharacters: Story = {
  render: () => ({
    components: { PlateReadout },
    setup: () => ({ read: ACCEPTED }),
    template: `<div style="max-width: 32rem">
      <PlateReadout :positions="read.positions" :fields="read.fields" :format="read.format" :plate="read.plate" />
    </div>`,
  }),
}

export const PlateUncertain: Story = {
  render: () => ({
    components: { PlateReadout },
    setup: () => ({ read: QUEUED }),
    template: `<div style="max-width: 32rem">
      <PlateReadout :positions="read.positions" :fields="read.fields" :format="read.format" :plate="read.plate" :minimum="0.002" />
    </div>`,
  }),
}

export const PlateNone: Story = {
  render: () => ({
    components: { PlateReadout },
    template: '<PlateReadout :positions="[]" :fields="null" :format="null" :plate="null" />',
  }),
}

export const Confidence: Story = {
  render: () => ({
    components: { ConfidenceBar },
    template: `<div style="display: grid; gap: 24px; max-width: 28rem">
      <ConfidenceBar :value="0.99999997" :threshold="0.9" />
      <ConfidenceBar :value="0.62" :threshold="0.9" />
      <ConfidenceBar :value="0.41" :threshold="null" :calibrated="false" label="Vote share" />
    </div>`,
  }),
}

export const PredictionSets: Story = {
  render: () => ({
    components: { PredictionSet },
    template: `<div style="display: grid; gap: 24px; max-width: 30rem">
      <PredictionSet :set="['27-د-9']" :level="0.95" prediction="27-د-9" />
      <PredictionSet :set="['27-د-9', '22-د-9', '227-د-9']" :level="0.9" prediction="27-د-9" />
      <PredictionSet :set="[]" :level="0.95" prediction="54-ب-4" />
      <PredictionSet :set="null" :level="null" prediction="54-ب-4" />
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

export const Views: Story = {
  render: () => ({
    components: { ViewCard },
    setup: () => ({ read: ACCEPTED }),
    template: `<div style="display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr))">
      <ViewCard v-for="view in read.views" :key="view.index" :view="view" />
    </div>`,
  }),
}

export const PhotoWithBox: Story = {
  render: () => ({
    components: { PhotoThumb },
    setup: () => ({ read: ACCEPTED }),
    template: `<div style="max-width: 24rem">
      <PhotoThumb src="/runtime/parity/scene_02.png" alt="Synthetic street photo (a parity fixture)" :box="read.views[2].box">
        View 3 · scene_02.png
      </PhotoThumb>
    </div>`,
  }),
}

export const Tray: Story = {
  render: () => ({
    components: { PhotoTray },
    setup: () => {
      const photos = ref<Photo[]>([photo(0), photo(1), photo(2)])
      const boxes = ACCEPTED.views.map((v) => v.box)
      function move(from: number, to: number) {
        const next = [...photos.value]
        const [item] = next.splice(from, 1)
        if (item) next.splice(to, 0, item)
        photos.value = next
      }
      return { photos, boxes, move }
    },
    template: `<div style="max-width: 36rem">
      <PhotoTray :photos="photos" :boxes="photos.map((p) => boxes[p.view] ?? null)" @move="move" />
    </div>`,
  }),
}

export const EmptyTray: Story = {
  render: () => ({
    components: { PhotoTray },
    template: '<div style="max-width: 36rem"><PhotoTray :photos="[]" /></div>',
  }),
}

export const ReadMode: Story = {
  render: () => ({
    components: { ModeToggle },
    template: '<div style="max-width: 32rem"><ModeToggle /></div>',
  }),
}
