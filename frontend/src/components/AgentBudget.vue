<script setup>
import { computed } from 'vue';
import { CAFFEINE_LIMIT, SUGAR_LIMIT } from '../config.js';
import { state } from '../state.js';

const analysis = computed(() => state.agentAnalysis || {});
const budgetCaffeine = computed(() => Number(analysis.value.budget_caffeine || CAFFEINE_LIMIT));
const budgetSugar = computed(() => Number(analysis.value.budget_sugar || SUGAR_LIMIT));
const consumedCaffeine = computed(() => Number(analysis.value.caffeine_total || 0));
const consumedSugar = computed(() => Number(analysis.value.sugar_total || 0));
const caffeinePercent = computed(() => getPercent(consumedCaffeine.value, budgetCaffeine.value));
const sugarPercent = computed(() => getPercent(consumedSugar.value, budgetSugar.value));

const badgeText = computed(() => {
  if (state.agentStatus === 'loading') return '分析中...';
  if (state.agentStatus === 'error') return '未连接';
  return analysis.value.risk_level || '分析完成';
});

const badgeColor = computed(() => {
  if (state.agentStatus === 'loading') return '#fbbf24';
  if (state.agentStatus === 'error') return '#94a3b8';
  if (analysis.value.risk_level === '低风险') return '#10b981';
  if (analysis.value.risk_level === '高风险') return '#ef4444';
  return '#f59e0b';
});

const advice = computed(() => {
  if (state.agentStatus === 'error') return '请确认后端 Python 服务已启动。';
  return analysis.value.advice
    || analysis.value.recommendation
    || analysis.value.message
    || '记录饮品后，Agent 会根据当天摄入更新平衡建议。';
});

function getPercent(value, limit) {
  if (!limit) return 0;
  return Math.min(Math.max((value / limit) * 100, 0), 100);
}

function formatNumber(value) {
  return Number(value || 0).toFixed(1);
}
</script>

<template>
  <section class="agent-section card glass agent-budget-section">
    <div class="section-header-row">
      <h3 class="card-title agent-budget-title">☕ 今日预算与平衡策略</h3>
      <span id="agent-risk-badge" class="badge agent-risk-badge" :style="{ background: badgeColor }">
        {{ badgeText }}
      </span>
    </div>

    <div class="agent-container agent-budget-container">
      <div class="agent-budget-metrics">
        <div class="agent-budget-row">
          <span>咖啡因剩余预算</span>
          <span id="caffeine-budget-text">{{ formatNumber(consumedCaffeine) }} / {{ formatNumber(budgetCaffeine) }} mg</span>
        </div>
        <div class="agent-budget-track">
          <div
            id="caffeine-budget-bar"
            class="agent-budget-fill"
            :style="{
              width: `${caffeinePercent}%`,
              background: caffeinePercent >= 100 ? '#ef4444' : '#c084fc',
            }"
          ></div>
        </div>

        <div class="agent-budget-row">
          <span>糖分剩余预算</span>
          <span id="sugar-budget-text">{{ formatNumber(consumedSugar) }} / {{ formatNumber(budgetSugar) }} g</span>
        </div>
        <div class="agent-budget-track">
          <div
            id="sugar-budget-bar"
            class="agent-budget-fill"
            :style="{
              width: `${sugarPercent}%`,
              background: sugarPercent >= 100 ? '#ef4444' : '#f472b6',
            }"
          ></div>
        </div>
      </div>
      <div id="agent-advice-text" class="agent-advice-text">{{ advice }}</div>
    </div>
  </section>
</template>

<style scoped>
.agent-budget-section {
  border: 2px solid #c084fc;
  background: rgba(192, 132, 252, 0.05);
  margin-bottom: 16px;
}

.agent-budget-title {
  color: #9b63cf;
}

.agent-risk-badge {
  color: #fff;
}

.agent-budget-container {
  padding-top: 15px;
}

.agent-budget-metrics {
  margin-bottom: 20px;
}

.agent-budget-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  font-size: 0.9rem;
}

.agent-budget-track {
  width: 100%;
  height: 8px;
  margin-bottom: 12px;
  overflow: hidden;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

.agent-budget-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.agent-advice-text {
  color: var(--text-secondary);
  font-size: 0.95rem;
  line-height: 1.5;
}
</style>
