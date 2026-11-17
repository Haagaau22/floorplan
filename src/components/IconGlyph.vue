<script setup lang="ts">
defineProps<{
  name: 'hand' | 'ruler' | 'area' | 'edit' | 'layers' | 'fit' | 'plus' | 'minus' | 'close' | 'search'
}>()
</script>

<template>
  <svg class="icon-glyph" viewBox="0 0 24 24" aria-hidden="true">
    <template v-if="name === 'hand'">
      <path d="M7.5 11V6.5a1.5 1.5 0 0 1 3 0V10m0-4.5a1.5 1.5 0 0 1 3 0V10m0-3.5a1.5 1.5 0 0 1 3 0v4m0-2a1.5 1.5 0 0 1 3 0v4.3c0 4.6-2.7 7.2-7.1 7.2H12c-2.2 0-3.7-.8-4.9-2.4L4.4 14a1.7 1.7 0 0 1 2.7-2Z" />
    </template>
    <template v-else-if="name === 'ruler'">
      <path d="m4.2 15.8 11.6-11.6 4 4-11.6 11.6-4-4Z" /><path d="m12.2 7.8 2 2m-5 1 2 2m-5 1 2 2" />
    </template>
    <template v-else-if="name === 'area'">
      <path d="m5 18 2-11 10-2 2 12-14 1Z" /><circle cx="5" cy="18" r="1.4" /><circle cx="7" cy="7" r="1.4" /><circle cx="17" cy="5" r="1.4" /><circle cx="19" cy="17" r="1.4" />
    </template>
    <template v-else-if="name === 'edit'">
      <path d="m4 16-.8 4 4-.8L18.5 7.9l-3.2-3.2L4 16Z" /><path d="m13.8 6.2 3.2 3.2M4 16l3.2 3.2" />
    </template>
    <template v-else-if="name === 'layers'">
      <path d="m12 3 8 4-8 4-8-4 8-4Z" /><path d="m4 11 8 4 8-4M4 15l8 4 8-4" />
    </template>
    <template v-else-if="name === 'fit'">
      <path d="M8 4H4v4m12-4h4v4M4 16v4h4m12-4v4h-4" />
    </template>
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14M5 12h14" />
    </template>
    <template v-else-if="name === 'minus'">
      <path d="M5 12h14" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="m6 6 12 12M18 6 6 18" />
    </template>
    <template v-else>
      <circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4 4" />
    </template>
  </svg>
</template>
