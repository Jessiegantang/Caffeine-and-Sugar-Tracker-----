<script setup>
defineProps({ total: Number, custom: Number });
defineEmits(['import', 'reset']);
</script>

<template>
  <section class="database-stats-card card glass">
    <div class="section-header-row">
      <h2 class="section-title">饮品数据库管理</h2>
      <div class="db-actions">
        <button type="button" class="btn btn-primary" @click="$emit('import')">批量导入</button>
        <button type="button" class="btn btn-danger" @click="$emit('reset')">重置数据库</button>
      </div>
    </div>
    <div class="db-stats-grid">
      <div class="db-stat-item"><span class="db-stat-value">{{ total }}</span><span class="db-stat-label">饮品总数</span></div>
      <div class="db-stat-item"><span class="db-stat-value">{{ custom }}</span><span class="db-stat-label">自定义饮品</span></div>
    </div>
  </section>
</template>
