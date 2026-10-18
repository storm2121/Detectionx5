import type { StorybookConfig } from '@storybook/vue3-vite'

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.ts'],
  addons: ['@storybook/addon-essentials', '@storybook/addon-a11y'],
  framework: { name: '@storybook/vue3-vite', options: {} },
  staticDirs: ['../public'],
  core: { disableTelemetry: true },
}

export default config
