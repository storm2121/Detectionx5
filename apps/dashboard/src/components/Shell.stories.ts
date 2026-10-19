import type { Meta, StoryObj } from '@storybook/vue3'

import AppBar from './AppBar.vue'
import AppFooter from './AppFooter.vue'
import TabBar from './TabBar.vue'

// The chrome around every page. The tab bar only appears at phone width, so its story
// renders it in a narrow frame.
const meta: Meta = { title: 'Shell' }
export default meta
type Story = StoryObj

export const TopBar: Story = {
  render: () => ({
    components: { AppBar },
    template: '<AppBar />',
  }),
}

export const Footer: Story = {
  render: () => ({
    components: { AppFooter },
    template: '<AppFooter />',
  }),
}

export const PhoneTabs: Story = {
  parameters: { viewport: { defaultViewport: 'mobile1' } },
  render: () => ({
    components: { TabBar },
    template: '<div style="position: relative; height: 5rem"><TabBar /></div>',
  }),
}
