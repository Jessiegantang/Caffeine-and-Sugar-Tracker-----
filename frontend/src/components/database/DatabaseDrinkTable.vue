<script setup>
import { TYPE_DEFINITIONS } from '../../drinks-database.js';

defineProps({ drinks: { type: Array, default: () => [] }, query: { type: String, default: '' }, total: Number });
const emit = defineEmits(['edit', 'update:query']);

function typeLabel(type) {
  return TYPE_DEFINITIONS[type]?.label || type || '其他';
}
</script>

<template>
  <section class="database-table-section card glass">
    <div class="database-table-header">
      <div><h3 class="card-title">数据库列表</h3><div class="database-search-count">{{ query ? `找到 ${drinks.length} / ${total} 条饮品` : `显示全部 ${total} 条饮品` }}</div></div>
      <div class="database-search-box">
        <input type="search" :value="query" placeholder="搜索品牌、饮品、类型或数值" @input="emit('update:query', $event.target.value)">
        <button type="button" class="database-search-clear" :disabled="!query" aria-label="清空搜索" @click="emit('update:query', '')">清空</button>
      </div>
    </div>
    <div class="table-container">
      <table class="drinks-table">
        <thead><tr><th>品牌</th><th>名称</th><th>类型</th><th>咖啡因 (mg)</th><th>糖分 (g)</th><th>容量 (ml)</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-if="!drinks.length"><td colspan="7" class="drinks-table-empty">没有找到匹配的饮品</td></tr>
          <tr v-for="drink in drinks" v-else :key="drink.id">
            <td>{{ drink.brand || '-' }}</td><td>{{ drink.name }}</td><td>{{ typeLabel(drink.type) }}</td>
            <td>{{ drink.caffeine }}</td><td>{{ drink.baseSugar }}</td><td>{{ drink.defaultVolume }}</td>
            <td><button type="button" class="table-edit-btn" :title="`编辑 ${drink.name}`" @click="emit('edit', drink)">编辑</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
