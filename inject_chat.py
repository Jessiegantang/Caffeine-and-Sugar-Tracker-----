import re
import os

html_path = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

chat_html = """
          <!-- Companion Chat UI -->
          <div class="chat-container card glass" style="padding: 16px; display: flex; flex-direction: column; height: 350px; margin-top: 16px;">
            <h3 class="card-title" style="margin-top: 0; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
              <span>☕</span> 交互小助手
            </h3>
            <div id="chat-history" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding-right: 8px; margin-bottom: 12px;">
              <!-- Messages go here -->
            </div>
            <div style="display: flex; gap: 8px;">
              <input id="chat-input" type="text" placeholder="问我任何问题..." style="flex: 1; padding: 10px 14px; border: 1px solid var(--border-color); border-radius: 8px; font-family: inherit; font-size: 0.95rem; outline: none; background: var(--bg-deep); color: var(--text-main);">
              <button id="chat-send-btn" style="background: var(--primary-gradient); color: white; border: none; border-radius: 8px; padding: 0 16px; font-weight: 600; cursor: pointer; transition: all 0.2s;">发送</button>
            </div>
          </div>
"""

# Replace the insights-section with chat_html
html = re.sub(
    r'<!-- Dynamic Daily Insights -->\s*<section class="insights-section card glass">.*?</section>',
    chat_html,
    html,
    flags=re.DOTALL
)

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
