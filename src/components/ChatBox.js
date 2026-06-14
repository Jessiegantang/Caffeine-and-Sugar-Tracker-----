import { state } from '../state.js';
import { agentActApi, fetchChatHistoryApi, sendChatMessageApi } from '../api.js';

const TEXT = {
  parsedTitle: '\u5df2\u8bc6\u522b\u996e\u54c1\u4fe1\u606f\uff0c\u5e76\u586b\u5165\u8868\u5355\u3002',
  parsedHint: '\u786e\u8ba4\u65e0\u8bef\u540e\uff0c\u53ef\u6dfb\u52a0\u5230\u5f53\u5929\u6444\u5165\u8bb0\u5f55\u3002',
  name: '\u540d\u79f0',
  volume: '\u5bb9\u91cf',
  sugar: '\u751c\u5ea6',
  missing: '\u7f3a\u5c11\u4fe1\u606f',
  none: '\u65e0',
  details: '\u6280\u672f\u8be6\u60c5 JSON',
  addLog: '\u6dfb\u52a0\u5230\u5f53\u5929\u6444\u5165\u8bb0\u5f55',
  added: '\u5df2\u63d0\u4ea4',
  intro: '\u5f55\u5165\u4eca\u5929\u7b2c\u4e00\u676f\u996e\u54c1\u5427\u3002\u4f60\u4e5f\u53ef\u4ee5\u76f4\u63a5\u5728\u8fd9\u91cc\u8ddf\u6211\u804a\u5929\u3002',
  sendFailed: '\u53d1\u9001\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u3002',
  send: '\u53d1\u9001',
};

const SUGAR_LABELS = {
  none: '\u65e0\u7cd6',
  three: '\u4e09\u5206\u7cd6',
  half: '\u534a\u7cd6',
  seven: '\u4e03\u5206\u7cd6',
  full: '\u5168\u7cd6',
  unknown: '\u672a\u77e5',
};

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
  const canAdd = missing.length === 0;
  if (!canAdd) return;

  const name = parsedIntake.name || parsedIntake.drink_name || parsedIntake.product_name || '-';
  const volume = parsedIntake.volume || parsedIntake.volume_ml || '-';
  const sugar = parsedIntake.sugar || parsedIntake.sugar_level || parsedIntake.sweetness || '-';
  const missingText = missing.length ? missing.join(', ') : TEXT.none;
  const sugarText = SUGAR_LABELS[sugar] || sugar;

  const card = document.createElement('div');
  card.className = 'chat-msg assistant';
  card.innerHTML = `
    <span class="chat-avatar">AI</span>
    <div class="chat-bubble assistant-bubble">
      <strong>${TEXT.parsedTitle}</strong>
      <p class="chat-parse-hint">${TEXT.parsedHint}</p>
      <div class="chat-parse-summary">
        <span>${TEXT.name}\uff1a${escapeHtml(name)}</span>
        <span>${TEXT.volume}\uff1a${escapeHtml(volume)}${volume === '-' ? '' : ' ml'}</span>
        <span>${TEXT.sugar}\uff1a${escapeHtml(sugarText)}</span>
        <span>${TEXT.missing}\uff1a${escapeHtml(missingText)}</span>
      </div>
      ${canAdd ? `<button type="button" class="chat-add-log-btn">${TEXT.addLog}</button>` : ''}
      <details class="chat-structured-details">
        <summary>${TEXT.details}</summary>
        <pre class="chat-json">${escapeHtml(JSON.stringify(parsedIntake, null, 2))}</pre>
      </details>
    </div>
  `;

  const addButton = card.querySelector('.chat-add-log-btn');
  addButton?.addEventListener('click', () => {
    addButton.disabled = true;
    addButton.textContent = TEXT.added;
    window.dispatchEvent(new CustomEvent('drinkmind:add-parsed-intake', {
      detail: parsedIntake,
    }));
  });

  container.appendChild(card);
  container.scrollTop = container.scrollHeight;

  window.dispatchEvent(new CustomEvent('drinkmind:intake-parsed', {
    detail: parsedIntake,
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

  container.innerHTML = '';
  if (history.length === 0) {
    container.innerHTML = `
      <div class="chat-msg assistant">
        <span class="chat-avatar">AI</span>
        <div class="chat-bubble assistant-bubble">
          ${TEXT.intro}
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
          ${escapeHtml(msg.content)}
        </div>
      `;
    } else {
      msgDiv.classList.add('assistant');
      msgDiv.innerHTML = `
        <span class="chat-avatar">AI</span>
        <div class="chat-bubble assistant-bubble">
          ${escapeHtml(msg.content)}
        </div>
      `;
    }
    container.appendChild(msgDiv);
  }

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

  const container = document.getElementById('chat-history');
  const tempMsg = document.createElement('div');
  tempMsg.className = 'chat-msg user';
  tempMsg.innerHTML = `
    <span class="chat-avatar">Me</span>
    <div class="chat-bubble user-bubble">
      ${escapeHtml(message)}
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
            detail: nutritionResult,
          }));
        }
      } catch (agentError) {
        console.error('Agent act estimate failed', agentError);
      }
    }
  } catch (e) {
    console.error('Chat error', e);
    alert(TEXT.sendFailed);
  } finally {
    btn.disabled = false;
    btn.textContent = TEXT.send;
  }
}
