import { state } from '../state.js';
import { fetchChatHistoryApi, sendChatMessageApi } from '../api.js';

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
      <div class="chat-msg assistant" style="display: flex; gap: 8px;">
        <span style="font-size: 1.2rem;">☕</span>
        <div style="background: rgba(192, 132, 252, 0.1); padding: 10px 14px; border-radius: 12px; border-top-left-radius: 2px; font-size: 0.95rem; line-height: 1.5; color: var(--text-secondary);">
          录入今日第一杯饮品，Agent将根据你的历史习惯为你生成今日的平衡策略。你也可以直接在这里跟我聊天哦！
        </div>
      </div>
    `;
    return;
  }
  
  for (const msg of history) {
    const msgDiv = document.createElement('div');
    msgDiv.style.display = 'flex';
    msgDiv.style.gap = '8px';
    
    if (msg.role === 'user') {
      msgDiv.style.flexDirection = 'row-reverse';
      msgDiv.innerHTML = `
        <span style="font-size: 1.2rem;">👤</span>
        <div style="background: linear-gradient(135deg, #a855f7, #c084fc); padding: 10px 14px; border-radius: 12px; border-top-right-radius: 2px; font-size: 0.95rem; line-height: 1.5; color: #ffffff; box-shadow: 0 2px 6px rgba(168, 85, 247, 0.25);">
          ${msg.content}
        </div>
      `;
    } else {
      msgDiv.innerHTML = `
        <span style="font-size: 1.2rem;">☕</span>
        <div style="background: rgba(255, 255, 255, 0.9); padding: 10px 14px; border-radius: 12px; border-top-left-radius: 2px; font-size: 0.95rem; line-height: 1.5; color: #334155; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
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
  tempMsg.style.display = 'flex';
  tempMsg.style.gap = '8px';
  tempMsg.style.flexDirection = 'row-reverse';
  tempMsg.innerHTML = `
    <span style="font-size: 1.2rem;">👤</span>
    <div style="background: linear-gradient(135deg, #a855f7, #c084fc); padding: 10px 14px; border-radius: 12px; border-top-right-radius: 2px; font-size: 0.95rem; line-height: 1.5; color: #ffffff; box-shadow: 0 2px 6px rgba(168, 85, 247, 0.25);">
      ${message}
    </div>
  `;
  container.appendChild(tempMsg);
  container.scrollTop = container.scrollHeight;

  try {
    await sendChatMessageApi(state.selectedDate, message);
    await fetchChatHistory();
  } catch (e) {
    console.error('Chat error', e);
    alert('发送失败，请检查网络');
  } finally {
    btn.disabled = false;
    btn.textContent = '发送';
  }
}
