import { Download, Moon } from '@lucide/vue'
import type { Meta, StoryObj } from '@storybook/vue3'
import { ref } from 'vue'

import ProgressBar from '../ProgressBar.vue'
import DisclosureSection from './DisclosureSection.vue'
import DxButton from './DxButton.vue'
import IconButton from './IconButton.vue'
import NoticeBlock from './NoticeBlock.vue'
import SegmentedControl from './SegmentedControl.vue'
import SelectField from './SelectField.vue'
import SkeletonBlock from './SkeletonBlock.vue'
import StatusLine from './StatusLine.vue'
import SwitchField from './SwitchField.vue'
import TextField from './TextField.vue'

// The console's headless controls, every one in both themes (the preview renders each story
// in a light and a dark frame side by side).
const meta: Meta = { title: 'Controls' }
export default meta
type Story = StoryObj

export const Buttons: Story = {
  render: () => ({
    components: { DxButton, IconButton },
    setup: () => ({ Download, Moon }),
    template: `<div style="display: grid; gap: 16px; justify-items: start">
      <div class="dx-row">
        <DxButton variant="primary">Read plate</DxButton>
        <DxButton>Upload and queue</DxButton>
        <DxButton variant="plain">Remove all photos</DxButton>
      </div>
      <div class="dx-row">
        <DxButton variant="primary" :icon="Download">Export 3 corrections</DxButton>
        <DxButton variant="primary" busy busy-label="Reading photos">Read plate</DxButton>
        <DxButton disabled>No corrections to export</DxButton>
        <DxButton variant="plain" size="small">Check for updates</DxButton>
      </div>
      <IconButton :icon="Moon" label="Switch to the dark theme" />
    </div>`,
  }),
}

export const Segmented: Story = {
  render: () => ({
    components: { SegmentedControl },
    setup: () => ({
      mode: ref('server'),
      set: ref('eval_synthetic'),
      modes: [
        { label: 'Server', value: 'server' },
        { label: 'In this browser', value: 'browser' },
      ],
      sets: [
        { label: 'Synthetic test set', value: 'eval_synthetic' },
        { label: 'Pseudo-real set', value: 'eval_pseudo_real' },
        { label: 'Multi-view sets', value: 'eval_views' },
      ],
    }),
    template: `<div style="display: grid; gap: 16px; justify-items: start">
      <SegmentedControl v-model="mode" :options="modes" label="Where the plate is read" />
      <SegmentedControl v-model="set" :options="sets" label="Evaluation set" size="small" />
    </div>`,
  }),
}

export const Fields: Story = {
  render: () => ({
    components: { SelectField, SwitchField, TextField },
    setup: () => ({
      on: ref(true),
      off: ref(false),
      good: ref('24830-ب-1'),
      bad: ref('2483'),
      empty: ref(''),
      choice: ref('crnn-beam'),
      recognizers: [
        { label: 'EasyOCR (baseline)', value: 'easyocr' },
        { label: 'CRNN, greedy', value: 'crnn-greedy' },
        { label: 'CRNN, constrained beam', value: 'crnn-beam' },
      ],
    }),
    template: `<div style="display: grid; gap: 20px; max-width: 28rem">
      <SwitchField v-model="on" label="Find the plate in each photo" hint="Switch off when every photo is already a plate crop." />
      <SwitchField v-model="off" label="A switch that is off" />
      <TextField v-model="good" label="Correct plate" plate hint="Reads as a standard plate: digits 24830, letter ب, region 1." />
      <TextField v-model="bad" label="Correct plate" plate error="Not a plate yet: digits, one of the six letters, then the region, as in 24830-ب-1; or digits then WW." />
      <TextField v-model="empty" label="Path under the jobs root" placeholder="batch-01" hint="Relative to PLATE_JOBS_ROOT on the service." />
      <SelectField v-model="choice" :options="recognizers" label="Recogniser" inline />
    </div>`,
  }),
}

export const Disclosure: Story = {
  render: () => ({
    components: { DisclosureSection },
    template: `<div style="display: grid; gap: 8px; max-width: 36rem">
      <DisclosureSection title="Views and hypotheses" summary="3 of 3 views read · product of posteriors" :level="2">
        <p>Each photo's best detection, read by the constrained beam.</p>
      </DisclosureSection>
      <DisclosureSection title="Open from the start" :open="true">
        <p>The content rises into place when opened and leaves the same way.</p>
      </DisclosureSection>
    </div>`,
  }),
}

export const Feedback: Story = {
  render: () => ({
    components: { NoticeBlock, ProgressBar, SkeletonBlock, StatusLine },
    template: `<div style="display: grid; gap: 16px; max-width: 36rem">
      <div class="dx-row">
        <StatusLine tone="ok" label="Accepted" />
        <StatusLine tone="warn" label="Sent to review: empty conformal set" />
        <StatusLine tone="bad" label="Failed" />
        <StatusLine tone="info" label="Reviewed" />
        <StatusLine label="Archived" />
      </div>
      <NoticeBlock><strong>Synthetic results are not real-world accuracy.</strong> Every set here is generated.</NoticeBlock>
      <NoticeBlock tone="warning" message="2 file(s) skipped: only images are read, at most 10 photos." />
      <NoticeBlock tone="error" title="The read failed" message="The plate service cannot be reached. Check that it is running, then press Read plate again." />
      <ProgressBar :value="0.42" label="Job progress" />
      <SkeletonBlock kind="plate" />
      <SkeletonBlock kind="table" :rows="3" />
    </div>`,
  }),
}
