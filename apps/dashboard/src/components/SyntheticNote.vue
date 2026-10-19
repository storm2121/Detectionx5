<script setup lang="ts">
import NoticeBlock from './ui/NoticeBlock.vue'

/** The label every synthetic figure carries (AGENT_RULES §1.3), with what it applies to. */
withDefaults(defineProps<{ detail?: string }>(), { detail: '' })
</script>

<template>
  <NoticeBlock tone="note" data-testid="synthetic-note">
    <span>
      <strong>Synthetic results are not real-world accuracy.</strong>
      <template v-if="detail">{{ ' ' + detail }}</template>
      <slot />
    </span>
  </NoticeBlock>
</template>
