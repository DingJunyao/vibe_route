<template>
  <div :class="{ active: isActive }">Test</div>
</template>

<script setup lang="ts">
const isActive = ref(false)
</script>
