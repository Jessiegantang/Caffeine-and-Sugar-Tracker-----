<script setup>
import { nextTick, ref, watch } from 'vue';
import {
  fetchChatHistoryApi,
  sendChatMessageStreamApi,
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

async function loadHistory() {
  if (!state.selectedDate) return;

  const currentRequest = ++historyRequest;
  error.value = '';
  try {
    const data = await fetchChatHistoryApi(state.selectedDate);
    if (currentRequest !== historyRequest) return;
    messages.value = data.history || [];
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
  const streamMessageId = `stream-${Date.now()}`;
  messages.value.push({ role: 'assistant', content: '', id: streamMessageId, streaming: true });
  await scrollToBottom();

  try {
    const data = await sendChatMessageStreamApi(state.selectedDate, message, async (event) => {
      const assistantMessage = messages.value.find((item) => item.id === streamMessageId);
      if (!assistantMessage) return;
      if (event.type === 'delta') assistantMessage.content += event.text || '';
      if (event.type === 'replace') assistantMessage.content = event.text || '';
      if (event.type === 'done') assistantMessage.streaming = false;
      await scrollToBottom();
    });

    const parsedIntake = data.parsed_intake;
    if (canAddParsedIntake(parsedIntake)) {
      messages.value.push({
        role: 'intake_card',
        id: data.trace_id || `intake-${Date.now()}`,
        parsed: { ...parsedIntake, submitted: false },
      });
      emitAppEvent(INTAKE_PARSED_EVENT, parsedIntake);
    }
    if (data.nutrition_result) {
      emitAppEvent(NUTRITION_RESULT_EVENT, data.nutrition_result);
    }
    await scrollToBottom();
  } catch {
    const assistantMessage = messages.value.find((item) => item.id === streamMessageId);
    if (assistantMessage && !assistantMessage.content) {
      messages.value = messages.value.filter((item) => item.id !== streamMessageId);
    } else if (assistantMessage) {
      assistantMessage.streaming = false;
    }
    error.value = '发送失败，请检查网络和后端服务。';
  } finally {
    sending.value = false;
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
        :key="message.id || `${message.role}-${index}-${message.content}`"
        class="chat-msg"
        :class="message.role === 'user' ? 'user' : 'assistant'"
      >
        <span class="chat-avatar">{{ message.role === 'user' ? 'Me' : 'AI' }}</span>
        <div
          v-if="message.role !== 'intake_card'"
          class="chat-bubble"
          :class="message.role === 'user' ? 'user-bubble' : 'assistant-bubble'"
        >
          {{ message.content }}
          <span v-if="message.streaming && !message.content" class="chat-stream-waiting">...</span>
          <span v-else-if="message.streaming" class="chat-stream-cursor" aria-hidden="true">▍</span>
        </div>
        <div v-else class="chat-bubble assistant-bubble intake-card-bubble">
          <strong>{{ message.parsed.submitted ? '已添加到当天摄入记录。' : '已识别饮品信息，并填入表单。' }}</strong>
          <p v-if="!message.parsed.submitted" class="chat-parse-hint">确认无误后，可添加到当天摄入记录。</p>
          <div class="chat-parse-summary">
            <span>名称：{{ getParsedName(message.parsed) }}</span>
            <span>容量：{{ getParsedVolume(message.parsed) }}{{ getParsedVolume(message.parsed) === '-' ? '' : ' ml' }}</span>
            <span>甜度：{{ getParsedSugar(message.parsed) }}</span>
          </div>
          <button
            type="button"
            class="chat-add-log-btn"
            :disabled="message.parsed.submitted"
            @click="addParsedIntake(message.parsed)"
          >
            {{ message.parsed.submitted ? '已添加' : '添加到当天摄入记录' }}
          </button>
          <details class="chat-structured-details">
            <summary>技术详情 JSON</summary>
            <pre class="chat-json">{{ JSON.stringify(message.parsed, null, 2) }}</pre>
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

.chat-stream-waiting,
.chat-stream-cursor {
  display: inline-block;
  animation: chat-stream-pulse 0.9s ease-in-out infinite;
}

@keyframes chat-stream-pulse {
  50% {
    opacity: 0.25;
  }
}
</style>
