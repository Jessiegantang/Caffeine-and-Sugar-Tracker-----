<script setup>
import { computed } from 'vue';
import { notifyDateChanged } from '../app-events.js';
import { CAFFEINE_LIMIT, SUGAR_LIMIT } from '../config.js';
import { useDailyMetrics } from '../composables/useDailyMetrics.js';
import { state } from '../state.js';

const RING_CIRCUMFERENCE = 377;
const { totalCaffeine, totalSugar } = useDailyMetrics();

const caffeineOffset = computed(() => getRingOffset(totalCaffeine.value, CAFFEINE_LIMIT));
const sugarOffset = computed(() => getRingOffset(totalSugar.value, SUGAR_LIMIT));

function formatNumber(value) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0';
}

function getRingOffset(value, limit) {
  const percentage = Math.min(Math.max(Number(value) / limit, 0), 1);
  return RING_CIRCUMFERENCE - (percentage * RING_CIRCUMFERENCE);
}

function selectDate(date) {
  if (!date) return;
  state.selectedDate = date;
  state.calendarMonth = date.slice(0, 7);
  notifyDateChanged(date);
}
</script>

<template>
  <section class="dashboard-section card glass">
    <div class="section-header-row">
      <h2 class="section-title">摄入数据看板</h2>
      <div class="filter-date-group">
        <label for="filter-date" class="sr-only">选择日期</label>
        <input
          id="filter-date"
          :value="state.selectedDate"
          type="date"
          class="date-selector-input"
          @change="selectDate($event.target.value)"
        >
      </div>
    </div>

    <div class="gauges-grid">
      <div class="gauge-card">
        <div class="gauge-circle-container">
          <svg class="progress-ring" width="140" height="140" aria-hidden="true">
            <circle
              class="progress-ring__background"
              stroke="rgba(255,255,255,0.05)"
              stroke-width="10"
              fill="transparent"
              r="60"
              cx="70"
              cy="70"
            />
            <circle
              id="caffeine-progress"
              class="progress-ring__bar progress-caffeine"
              stroke="url(#caffeine-gradient)"
              stroke-width="10"
              stroke-linecap="round"
              fill="transparent"
              r="60"
              cx="70"
              cy="70"
              :stroke-dasharray="RING_CIRCUMFERENCE"
              :stroke-dashoffset="caffeineOffset"
            />
          </svg>
          <div class="gauge-value-container">
            <span id="caffeine-total" class="gauge-value">{{ formatNumber(totalCaffeine) }}</span>
            <span class="gauge-unit">mg</span>
          </div>
        </div>
        <div class="gauge-label">
          <h3>咖啡因摄入</h3>
          <p>日推荐限量 {{ CAFFEINE_LIMIT }} mg</p>
        </div>
      </div>

      <div class="gauge-card">
        <div class="gauge-circle-container">
          <svg class="progress-ring" width="140" height="140" aria-hidden="true">
            <circle
              class="progress-ring__background"
              stroke="rgba(255,255,255,0.05)"
              stroke-width="10"
              fill="transparent"
              r="60"
              cx="70"
              cy="70"
            />
            <circle
              id="sugar-progress"
              class="progress-ring__bar progress-sugar"
              stroke="url(#sugar-gradient)"
              stroke-width="10"
              stroke-linecap="round"
              fill="transparent"
              r="60"
              cx="70"
              cy="70"
              :stroke-dasharray="RING_CIRCUMFERENCE"
              :stroke-dashoffset="sugarOffset"
            />
          </svg>
          <div class="gauge-value-container">
            <span id="sugar-total" class="gauge-value">{{ formatNumber(totalSugar) }}</span>
            <span class="gauge-unit">g</span>
          </div>
        </div>
        <div class="gauge-label">
          <h3>糖分摄入</h3>
          <p>日推荐限量 {{ SUGAR_LIMIT }} g</p>
        </div>
      </div>
    </div>
  </section>
</template>
