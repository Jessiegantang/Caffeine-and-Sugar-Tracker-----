<script setup>
defineProps({
  activeTab: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(['select']);
</script>

<template>
  <nav class="tabs-container glass" aria-label="主功能导航">
    <button
      class="tab-btn"
      :class="{ active: activeTab === 'tab-daily' }"
      data-tab="tab-daily"
      :aria-current="activeTab === 'tab-daily' ? 'page' : undefined"
      @click="emit('select', 'tab-daily')"
    >
      <svg
        class="tab-icon"
        viewBox="0 0 24 24"
        width="16"
        height="16"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
      单日记录与分析
    </button>

    <button
      class="tab-btn"
      :class="{ active: activeTab === 'tab-database' }"
      data-tab="tab-database"
      :aria-current="activeTab === 'tab-database' ? 'page' : undefined"
      @click="emit('select', 'tab-database')"
    >
      <svg
        class="tab-icon"
        viewBox="0 0 24 24"
        width="16"
        height="16"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path d="M12 19V10" />
        <polyline points="5 19 12 12 19 19" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      数据库管理
    </button>

    <a class="agent-jump-btn agent-jump-btn-muted" href="#agent-workspace">估算修正</a>
  </nav>
</template>
