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
