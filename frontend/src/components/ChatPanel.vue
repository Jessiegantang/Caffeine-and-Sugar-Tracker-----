<script setup>
import { nextTick, ref, watch } from 'vue';
import {
  agentActApi,
  fetchChatHistoryApi,
  sendChatMessageApi,
} from '../api.js';
import {
  ADD_PARSED_INTAKE_EVENT,
  emitAppEvent,
  INTAKE_PARSED_EVENT,
  NUTRITION_RESULT_EVENT,
} from '../app-events.js';
import { state } from '../state.js';

const historyContainer = ref(null);
const messages = ref([]);
const parsedIntakes = ref([]);
const input = ref('');
const sending = ref(false);
const error = ref('');
let historyRequest = 0;

const sugarLabels = {
  none: '无糖',
  three: '三分糖',
  half: '半糖',
  seven: '七分糖',
  full: '全糖',
  unknown: '未知',
};

watch(() => state.selectedDate, () => loadHistory(), { immediate: true });

async function loadHistory(clearParsed = true) {
  if (!state.selectedDate) return;

  const currentRequest = ++historyRequest;
  error.value = '';
  try {
    const data = await fetchChatHistoryApi(state.selectedDate);
    if (currentRequest !== historyRequest) return;
    messages.value = data.history || [];
    if (clearParsed) parsedIntakes.value = [];
    await scrollToBottom();
  } catch {
    if (currentRequest !== historyRequest) return;
    error.value = '聊天记录加载失败，请检查后端连接。';
  }
}

async function sendMessage() {
  const message = input.value.trim();
  if (!message || sending.value) return;

  input.value = '';
  sending.value = true;
  error.value = '';
  messages.value.push({ role: 'user', content: message });
  await scrollToBottom();

  try {
    const data = await sendChatMessageApi(state.selectedDate, message);
    await loadHistory(false);

    const parsedIntake = data.parsed_intake;
    if (canAddParsedIntake(parsedIntake)) {
      parsedIntakes.value.push({ ...parsedIntake, submitted: false });
      emitAppEvent(INTAKE_PARSED_EVENT, parsedIntake);
      await estimateParsedIntake(message);
    }
    await scrollToBottom();
  } catch {
    error.value = '发送失败，请检查网络和后端服务。';
  } finally {
    sending.value = false;
  }
}

async function estimateParsedIntake(message) {
  try {
    const action = await agentActApi(state.selectedDate, message);
    const nutritionResult = action.agent_state?.nutrition_result;
    if (nutritionResult) {
      emitAppEvent(NUTRITION_RESULT_EVENT, nutritionResult);
    }
  } catch (agentError) {
    console.error('Agent act estimate failed', agentError);
  }
}

function canAddParsedIntake(parsedIntake) {
  return parsedIntake?.intent === 'log_drink'
    && (!parsedIntake.missing_fields || parsedIntake.missing_fields.length === 0);
}

function addParsedIntake(parsedIntake) {
  parsedIntake.submitted = true;
  emitAppEvent(ADD_PARSED_INTAKE_EVENT, parsedIntake);
}

function getParsedName(parsedIntake) {
  return parsedIntake.name || parsedIntake.drink_name || parsedIntake.product_name || '-';
}

function getParsedVolume(parsedIntake) {
  return parsedIntake.volume || parsedIntake.volume_ml || '-';
}

function getParsedSugar(parsedIntake) {
  const sugar = parsedIntake.sugar || parsedIntake.sugar_level || parsedIntake.sweetness || '-';
  return sugarLabels[sugar] || sugar;
}

async function scrollToBottom() {
  await nextTick();
  if (historyContainer.value) {
    historyContainer.value.scrollTop = historyContainer.value.scrollHeight;
  }
}
</script>

<template>
  <section class="chat-container glass chat-panel">
    <h3 class="chat-panel-title"><span>☕</span> 交互小助手</h3>

    <div id="chat-history" ref="historyContainer" class="chat-history">
      <div v-if="!messages.length && !error" class="chat-msg assistant">
        <span class="chat-avatar">AI</span>
        <div class="chat-bubble assistant-bubble">
          录入今天第一杯饮品吧。你也可以直接在这里跟我聊天。
        </div>
      </div>

      <div
        v-for="(message, index) in messages"
        :key="`${message.role}-${index}-${message.content}`"
        class="chat-msg"
        :class="message.role === 'user' ? 'user' : 'assistant'"
      >
        <span class="chat-avatar">{{ message.role === 'user' ? 'Me' : 'AI' }}</span>
        <div class="chat-bubble" :class="message.role === 'user' ? 'user-bubble' : 'assistant-bubble'">
          {{ message.content }}
        </div>
      </div>

      <div v-for="(parsed, index) in parsedIntakes" :key="`parsed-${index}`" class="chat-msg assistant">
        <span class="chat-avatar">AI</span>
        <div class="chat-bubble assistant-bubble">
          <strong>已识别饮品信息，并填入表单。</strong>
          <p class="chat-parse-hint">确认无误后，可添加到当天摄入记录。</p>
          <div class="chat-parse-summary">
            <span>名称：{{ getParsedName(parsed) }}</span>
            <span>容量：{{ getParsedVolume(parsed) }}{{ getParsedVolume(parsed) === '-' ? '' : ' ml' }}</span>
            <span>甜度：{{ getParsedSugar(parsed) }}</span>
          </div>
          <button
            type="button"
            class="chat-add-log-btn"
            :disabled="parsed.submitted"
            @click="addParsedIntake(parsed)"
          >
            {{ parsed.submitted ? '已提交' : '添加到当天摄入记录' }}
          </button>
          <details class="chat-structured-details">
            <summary>技术详情 JSON</summary>
            <pre class="chat-json">{{ JSON.stringify(parsed, null, 2) }}</pre>
          </details>
        </div>
      </div>

      <p v-if="error" class="chat-panel-error">{{ error }}</p>
    </div>

    <form class="chat-input-row" @submit.prevent="sendMessage">
      <input id="chat-input" v-model="input" type="text" placeholder="问我任何问题..." :disabled="sending">
      <button id="chat-send-btn" type="submit" :disabled="sending || !input.trim()">
        {{ sending ? '...' : '发送' }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 550px;
  margin-top: 16px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
}

.chat-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  color: #475569;
  font-size: 1.1rem;
}

.chat-history {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
  padding-right: 8px;
  overflow-y: auto;
}

.chat-input-row {
  display: flex;
  gap: 8px;
}

.chat-input-row input {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.8);
  font: inherit;
}

.chat-input-row button {
  padding: 0 16px;
  border: none;
  border-radius: 6px;
  background: #1f2a2e;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}

.chat-input-row button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.chat-panel-error {
  color: #c24141;
  font-size: 0.85rem;
  text-align: center;
}
</style>
