<script setup>
import { computed } from 'vue';
import { notifyLogDelete, notifyLogSelected } from '../app-events.js';
import { useDailyMetrics } from '../composables/useDailyMetrics.js';

const { dailyLogs } = useDailyMetrics();

const sortedLogs = computed(() => [...dailyLogs.value].sort((left, right) => (
  String(right.startTime || '').localeCompare(String(left.startTime || ''))
)));

function getTypeIcon(type) {
  return {
    coffee: '☕',
    teacoffee: '🥥',
    tea: '🍵',
    milktea: '🧋',
    fruittea: '🍋',
    soda: '🥤',
  }[type] || '🥤';
}

function getTypeLabel(type) {
  return {
    coffee: '咖啡',
    teacoffee: '茶咖',
    tea: '原叶茶',
    milktea: '奶茶',
    fruittea: '果茶',
    soda: '汽水',
  }[type] || '其他';
}

function getSugarLabel(sugar) {
  return {
    none: '不另外加糖 (0%)',
    unknown: '糖分未知 (自动估算)',
    three: '三分糖 (30%)',
    half: '半糖 (50%)',
    seven: '七分糖 (70%)',
    full: '全糖 (100%)',
  }[sugar] || '未知';
}

function getReasoning(log) {
  const reasoning = log.explainability?.reasoning || log.reasoning;
  if (Array.isArray(reasoning)) return reasoning.filter(Boolean);
  return reasoning ? [String(reasoning)] : [];
}

function getMetaItems(log) {
  return [
    ['来源', log.data_source],
    ['方法', log.estimation_method],
    ['知识库', log.matched_knowledge_id],
    ['检索分', log.retrieval_score == null ? null : Number(log.retrieval_score).toFixed(3)],
    ['追踪', log.agent_trace_id],
  ].filter(([, value]) => value !== undefined && value !== null && value !== '');
}

function openExplainability(event, log) {
  if (event.target.closest('.log-del-btn, .log-explainability')) return;
  notifyLogSelected(log);
}
</script>

<template>
  <section class="logs-section card glass">
    <div class="section-header-row">
      <h3 class="card-title">该日饮用记录</h3>
      <span id="logs-count" class="badge count-badge">{{ dailyLogs.length }}</span>
    </div>

    <div class="logs-list-container">
      <div v-if="!dailyLogs.length" id="logs-empty" class="logs-empty-msg">
        <div class="empty-icon">☕</div>
        <p>该日期尚无任何摄入记录</p>
        <p class="empty-hint">在左侧录入或使用模板，记录饮品吧！</p>
      </div>

      <div v-else id="logs-list" class="logs-list">
        <div
          v-for="log in sortedLogs"
          :key="log.id"
          class="log-card"
          :class="`type-${log.type}`"
          tabindex="0"
          title="查看已保存的营养估算说明"
          @click="openExplainability($event, log)"
          @keydown.enter.self="notifyLogSelected(log)"
          @keydown.space.self.prevent="notifyLogSelected(log)"
        >
          <div class="log-card-left">
            <div class="log-type-icon">{{ getTypeIcon(log.type) }}</div>
            <div class="log-info-meta">
              <div class="log-title-row">
                <span v-if="log.brand" class="log-brand">{{ log.brand }}</span>
                <span class="log-name">{{ log.name }}</span>
                <span class="log-type-badge">{{ getTypeLabel(log.type) }}</span>
                <span
                  class="log-explainability-badge"
                  :class="log.explainability ? 'is-saved' : 'is-missing'"
                >
                  {{ log.explainability ? '可解释' : '暂无估算说明' }}
                </span>
              </div>
              <div class="log-time-range">
                ⏰ 饮用时间：{{ log.startTime }} - {{ log.endTime }}
                ({{ log.volume }}ml | {{ getSugarLabel(log.sugar) }})
              </div>

              <div
                v-if="log.data_source || log.estimation_method || log.reasoning || log.explainability"
                class="log-explainability"
              >
                <div class="explain-header">
                  <span>营养估算流程</span>
                  <strong v-if="log.confidence !== undefined">{{ Math.round(Number(log.confidence) * 100) }}%</strong>
                </div>
                <div class="explain-chips">
                  <span v-for="([label, value]) in getMetaItems(log)" :key="label" class="explain-chip">
                    {{ label }}: {{ value }}
                  </span>
                </div>
                <ul v-if="getReasoning(log).length" class="explain-reasoning">
                  <li v-for="reason in getReasoning(log)" :key="reason">{{ reason }}</li>
                </ul>
              </div>
            </div>
          </div>

          <div class="log-stats">
            <div v-if="log.isCalculating" class="log-stat-item" style="color: #a855f7; font-weight: 600;">
              <span class="log-stat-val">⏳ Agent 推断中...</span>
            </div>
            <template v-else>
              <div class="log-stat-item">
                <span class="log-stat-label">估算咖啡因</span>
                <span class="log-stat-val caffeine-num">{{ log.caffeine }} mg</span>
              </div>
              <div class="log-stat-item">
                <span class="log-stat-label">估算糖分</span>
                <span class="log-stat-val sugar-num">{{ log.sugarContent }} g</span>
              </div>
            </template>
            <button
              type="button"
              class="log-del-btn"
              title="删除记录"
              aria-label="删除记录"
              @click.stop="notifyLogDelete(log.id)"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
