<script setup>
import { ref, watch } from 'vue';
import { fetchDailyReportApi } from '../api.js';
import { CAFFEINE_LIMIT, SUGAR_LIMIT } from '../config.js';
import { useDailyMetrics } from '../composables/useDailyMetrics.js';
import { state } from '../state.js';

const { dailyLogs, totalCaffeine, totalSugar } = useDailyMetrics();
const insights = ref([]);
const loading = ref(false);
const error = ref('');
let requestId = 0;

watch(
  [() => state.selectedDate, () => state.logs],
  loadInsights,
  { immediate: true, deep: true },
);

async function loadInsights() {
  const currentRequest = ++requestId;
  error.value = '';

  if (!dailyLogs.value.length) {
    loading.value = false;
    insights.value = [{
      level: 'info',
      icon: '💧',
      title: '开始记录饮品',
      message: '记录下今天的第一杯饮品，Agent 将自动为您生成有温度的摄入分析。',
    }];
    return;
  }

  loading.value = true;
  try {
    const data = await fetchDailyReportApi(state.selectedDate);
    if (currentRequest !== requestId) return;
    insights.value = data.insights?.length
      ? data.insights
      : buildFallbackInsights(totalCaffeine.value, totalSugar.value);
  } catch {
    if (currentRequest !== requestId) return;
    error.value = '无法连接到 DrinkMind Agent。';
    insights.value = buildFallbackInsights(totalCaffeine.value, totalSugar.value);
  } finally {
    if (currentRequest === requestId) loading.value = false;
  }
}

function buildFallbackInsights(caffeine, sugar) {
  const warnings = [];
  if (sugar > SUGAR_LIMIT) {
    warnings.push({
      level: 'warning',
      icon: '⚠️',
      title: '今日糖分已经超出预算',
      message: `今天糖分约 ${sugar.toFixed(1)}g，已经超过 ${SUGAR_LIMIT}g 的日建议限量。后续饮品建议优先选择无糖茶、无糖美式或白水。`,
    });
  }
  if (caffeine > CAFFEINE_LIMIT) {
    warnings.push({
      level: 'warning',
      icon: '⚠️',
      title: '今日咖啡因已经超出预算',
      message: `今天咖啡因约 ${caffeine.toFixed(1)}mg，已经超过 ${CAFFEINE_LIMIT}mg 的日建议限量。后续建议避免继续摄入含咖啡因饮品。`,
    });
  }
  if (warnings.length) return warnings;

  if (sugar > SUGAR_LIMIT * 0.8 || caffeine > CAFFEINE_LIMIT * 0.8) {
    return [{
      level: 'info',
      icon: 'ℹ️',
      title: '今日摄入接近预算上限',
      message: `目前咖啡因约 ${caffeine.toFixed(1)}mg，糖分约 ${sugar.toFixed(1)}g。接下来可以选择低糖或无咖啡因饮品。`,
    }];
  }

  return [{
    level: 'success',
    icon: '✅',
    title: '今日饮品摄入控制良好',
    message: `目前咖啡因约 ${caffeine.toFixed(1)}mg，糖分约 ${sugar.toFixed(1)}g，仍在日建议范围内。`,
  }];
}
</script>

<template>
  <section class="insights-section card glass">
    <h3 class="card-title">该日摄入分析报告</h3>
    <div class="insights-container">
      <div id="insights-list" class="insights-list">
        <div v-if="loading" class="insights-status">正在由 DrinkMind Agent 生成今日摄入分析...</div>
        <div v-else-if="error" class="insights-status insights-status-error">{{ error }}</div>
        <div
          v-for="insight in insights"
          :key="`${insight.level}-${insight.title}`"
          class="insight-item"
          :class="`level-${insight.level}`"
        >
          <div class="insight-icon">{{ insight.icon }}</div>
          <div class="insight-content">
            <h4>{{ insight.title }}</h4>
            <p>{{ insight.message }}</p>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.insights-status {
  color: #64748b;
  padding: 20px;
  text-align: center;
}

.insights-status-error {
  color: #ef4444;
}
</style>
