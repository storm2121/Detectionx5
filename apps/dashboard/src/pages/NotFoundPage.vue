<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="dx-page">
    <header class="dx-page-head">
      <h1>Page not found</h1>
      <p>
        There is no page at this address. <RouterLink to="/read">Read a plate</RouterLink> instead.
      </p>
    </header>
  </div>
</template>
