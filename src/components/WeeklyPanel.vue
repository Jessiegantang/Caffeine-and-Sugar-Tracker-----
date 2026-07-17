<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { fetchWeeklyReportApi } from '../api.js';
import { renderWeeklyChart } from '../chart.js';
import { getWeeklyLogs } from '../storage.js';
import { state } from '../state.js';

const chartContainer = ref(null);
const insights = ref([]);
const loading = ref(false);
const error = ref('');
const today = getLocalDateString();
let requestId = 0;

const weekData = computed(() => getWeeklyLogs(state.logs, today));
const totalCaffeine = computed(() => weekData.value.weeklyLogs.reduce(
  (sum, log) => sum + Number(log.caffeine || 0),
  0,
));
const totalSugar = computed(() => weekData.value.weeklyLogs.reduce(
  (sum, log) => sum + Number(log.sugarContent || 0),
  0,
));
const activeDays = computed(() => new Set(
  weekData.value.weeklyLogs.map((log) => log.date),
).size);

watch(() => state.logs, refreshPanel, { immediate: true, deep: true });

function getLocalDateString() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatNumber(value) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0';
}

async function refreshPanel() {
  await nextTick();
  renderWeeklyChart(chartContainer.value, state.logs, weekData.value.weekDates);
  await loadInsights();
}

async function loadInsights() {
  const currentRequest = ++requestId;
  error.value = '';

  if (!weekData.value.weeklyLogs.length) {
    loading.value = false;
    insights.value = [];
    return;
  }

  loading.value = true;
  try {
    const data = await fetchWeeklyReportApi(today);
    if (currentRequest !== requestId) return;
    insights.value = data.insights?.length
      ? data.insights
      : [{
          level: 'success',
          icon: '🌟',
          title: '本周趋势良好',
          message: '本周各项饮品指标保持在建议范围内。',
        }];
  } catch {
    if (currentRequest !== requestId) return;
    error.value = '无法连接到 DrinkMind Agent。';
    insights.value = [];
  } finally {
    if (currentRequest === requestId) loading.value = false;
  }
}
</script>

<template>
  <div class="weekly-panel">
    <section class="weekly-stats-card card glass">
      <h2 class="section-title">近 7 天累计报告</h2>
      <div class="weekly-aggregates-grid">
        <div class="agg-card">
          <div class="agg-val-row">
            <span id="weekly-caffeine-total" class="agg-val num-caffeine">{{ formatNumber(totalCaffeine) }}</span>
            <span class="agg-unit">mg</span>
          </div>
          <span class="agg-label">周咖啡因总摄入</span>
        </div>
        <div class="agg-card">
          <div class="agg-val-row">
            <span id="weekly-sugar-total" class="agg-val num-sugar">{{ formatNumber(totalSugar) }}</span>
            <span class="agg-unit">g</span>
          </div>
          <span class="agg-label">周糖分总摄入</span>
        </div>
        <div class="agg-card">
          <div class="agg-val-row">
            <span id="weekly-active-days" class="agg-val">{{ activeDays }}</span>
            <span class="agg-unit">天</span>
          </div>
          <span class="agg-label">饮品打卡天数</span>
        </div>
      </div>
    </section>

    <section class="chart-card card glass">
      <h3 class="card-title">近 7 日摄入趋势 (占推荐日限额比例)</h3>
      <div class="chart-legends-row">
        <span class="legend-item"><span class="legend-dot dot-caffeine"></span> 咖啡因</span>
        <span class="legend-item"><span class="legend-dot dot-sugar"></span> 糖分</span>
      </div>
      <div id="weekly-chart-container" ref="chartContainer" class="chart-container-box"></div>
    </section>

    <section class="weekly-insights-section card glass">
      <h3 class="card-title">周度健康关联评估</h3>
      <div class="weekly-insights-container">
        <div id="weekly-insights-list" class="insights-list">
          <div v-if="!weekData.weeklyLogs.length" class="weekly-status">过去 7 天没有饮品记录。</div>
          <div v-else-if="loading" class="weekly-status">正在由 DrinkMind Agent 生成周度关联评估...</div>
          <div v-else-if="error" class="weekly-status is-error">{{ error }}</div>
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
  </div>
</template>

<style scoped>
.weekly-status {
  color: #64748b;
  padding: 20px;
  text-align: center;
}

.weekly-status.is-error {
  color: #ef4444;
}
</style>
