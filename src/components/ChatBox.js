import { state } from '../state.js';
import { agentActApi, fetchChatHistoryApi, sendChatMessageApi } from '../api.js';

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function appendParsedIntake(parsedIntake) {
  const container = document.getElementById('chat-history');
  if (!container || !parsedIntake || parsedIntake.intent !== 'log_drink') return;

  const missing = parsedIntake.missing_fields || [];
  const name = parsedIntake.name || parsedIntake.drink_name || parsedIntake.product_name || '-';
  const volume = parsedIntake.volume || parsedIntake.volume_ml || '-';
  const sugar = parsedIntake.sugar || parsedIntake.sugar_level || parsedIntake.sweetness || '-';
  const missingText = missing.length ? missing.join(', ') : 'None';

  const card = document.createElement('div');
  card.className = 'chat-msg assistant';
  card.innerHTML = `
    <span class="chat-avatar">AI</span>
    <div class="chat-bubble assistant-bubble">
      <strong>Recognized drink details and filled the form.</strong>
      <div class="chat-parse-summary">
        <span>name: ${escapeHtml(name)}</span>
        <span>volume: ${escapeHtml(volume)}${volume === '-' ? '' : ' ml'}</span>
        <span>sugar: ${escapeHtml(sugar)}</span>
        <span>missing: ${escapeHtml(missingText)}</span>
      </div>
      <details class="chat-structured-details">
        <summary>Structured JSON</summary>
        <pre class="chat-json">${escapeHtml(JSON.stringify(parsedIntake, null, 2))}</pre>
      </details>
    </div>
  `;
  container.appendChild(card);
  container.scrollTop = container.scrollHeight;

  window.dispatchEvent(new CustomEvent('drinkmind:intake-parsed', {
    detail: parsedIntake
  }));
}

export async function fetchChatHistory() {
  try {
    const data = await fetchChatHistoryApi(state.selectedDate);
    renderChatHistory(data.history || []);
  } catch (e) {
    console.error('Failed to fetch chat history', e);
  }
}

export function renderChatHistory(history) {
  const container = document.getElementById('chat-history');
  if (!container) return;
  
  container.innerHTML = ''; // clear
  if (history.length === 0) {
    container.innerHTML = `
      <div class="chat-msg assistant">
        <span class="chat-avatar">AI</span>
        <div class="chat-bubble assistant-bubble">
          录入今日第一杯饮品，Agent将根据你的历史习惯为你生成今日的平衡策略。你也可以直接在这里跟我聊天哦！
        </div>
      </div>
    `;
    return;
  }
  
  for (const msg of history) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'chat-msg';
    
    if (msg.role === 'user') {
      msgDiv.classList.add('user');
      msgDiv.innerHTML = `
        <span class="chat-avatar">Me</span>
        <div class="chat-bubble user-bubble">
          ${msg.content}
        </div>
      `;
    } else {
      msgDiv.classList.add('assistant');
      msgDiv.innerHTML = `
        <span class="chat-avatar">AI</span>
        <div class="chat-bubble assistant-bubble">
          ${msg.content}
        </div>
      `;
    }
    container.appendChild(msgDiv);
  }
  
  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

export async function handleSendMessage() {
  const input = document.getElementById('chat-input');
  const btn = document.getElementById('chat-send-btn');
  if (!input || !btn || !input.value.trim()) return;
  
  const message = input.value.trim();
  input.value = '';
  btn.disabled = true;
  btn.textContent = '...';
  
  // Optimistically add to UI
  const container = document.getElementById('chat-history');
  const tempMsg = document.createElement('div');
  tempMsg.className = 'chat-msg user';
  tempMsg.innerHTML = `
    <span class="chat-avatar">Me</span>
    <div class="chat-bubble user-bubble">
      ${message}
    </div>
  `;
  container.appendChild(tempMsg);
  container.scrollTop = container.scrollHeight;

  try {
    const data = await sendChatMessageApi(state.selectedDate, message);
    await fetchChatHistory();
    appendParsedIntake(data.parsed_intake);
    if (
      data.parsed_intake &&
      data.parsed_intake.intent === 'log_drink' &&
      (!data.parsed_intake.missing_fields || data.parsed_intake.missing_fields.length === 0)
    ) {
      try {
        const action = await agentActApi(state.selectedDate, message);
        const nutritionResult = action.agent_state?.nutrition_result;
        if (nutritionResult) {
          window.dispatchEvent(new CustomEvent('drinkmind:nutrition-result', {
            detail: nutritionResult
          }));
        }
      } catch (agentError) {
        console.error('Agent act estimate failed', agentError);
      }
    }
  } catch (e) {
    console.error('Chat error', e);
    alert('发送失败，请检查网络');
  } finally {
    btn.disabled = false;
    btn.textContent = '发送';
  }
}
