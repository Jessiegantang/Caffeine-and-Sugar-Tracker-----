<script setup>
import { ref } from 'vue';
import { saveSleepDataApi } from '../api.js';
import { notifySleepSaved } from '../app-events.js';
import { state } from '../state.js';

const hours = ref(null);
const saving = ref(false);
const status = ref('');
const statusType = ref('');

async function saveSleep() {
  const value = Number(hours.value);
  if (!Number.isFinite(value) || value <= 0 || value > 24) {
    status.value = '请输入 0-24 小时之间的睡眠时长。';
    statusType.value = 'error';
    return;
  }

  saving.value = true;
  status.value = '';
  try {
    await saveSleepDataApi(state.selectedDate, value);
    status.value = '睡眠数据已同步给 Agent。';
    statusType.value = 'success';
    notifySleepSaved(state.selectedDate);
  } catch {
    status.value = '保存失败，请检查后端是否开启。';
    statusType.value = 'error';
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section class="form-section card glass sleep-entry-section">
    <div class="section-header-row">
      <h3 class="card-title">睡眠补录</h3>
      <span class="sleep-entry-date">{{ state.selectedDate }}</span>
    </div>
    <form class="sleep-entry-form" @submit.prevent="saveSleep">
      <div class="form-group sleep-entry-input">
        <label for="input-sleep" class="sr-only">睡眠时长</label>
        <input
          id="input-sleep"
          v-model.number="hours"
          type="number"
          class="form-control"
          placeholder="睡眠时长 (小时)"
          min="0.5"
          max="24"
          step="0.5"
          required
        >
      </div>
      <button id="save-sleep-btn" type="submit" class="btn btn-primary" :disabled="saving">
        {{ saving ? '保存中...' : '保存' }}
      </button>
    </form>
    <p v-if="status" class="sleep-entry-status" :class="`is-${statusType}`">{{ status }}</p>
  </section>
</template>

<style scoped>
.sleep-entry-section {
  margin-top: 16px;
}

.sleep-entry-date {
  color: var(--text-muted);
  font-size: 0.8rem;
}

.sleep-entry-form {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.sleep-entry-input {
  flex: 1;
  margin-bottom: 0;
}

.sleep-entry-status {
  margin-top: 8px;
  font-size: 0.82rem;
}

.sleep-entry-status.is-success {
  color: var(--caffeine-primary);
}

.sleep-entry-status.is-error {
  color: #c24141;
}
</style>
