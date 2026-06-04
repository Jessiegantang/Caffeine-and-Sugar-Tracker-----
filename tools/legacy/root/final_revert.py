import shutil
import re
import os

src_html = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\index.html'
src_css = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\style.css'
dest_html = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html'
dest_css = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css'

# 1. Restore exact May 28 files
shutil.copy2(src_html, dest_html)
shutil.copy2(src_css, dest_css)

# 2. Inject Chat Assistant into index.html WITHOUT touching the Daily Analysis
with open(dest_html, 'r', encoding='utf-8') as f:
    html = f.read()

chat_html = """
          <!-- Dynamic Daily Insights -->
          <section class="insights-section card glass">
            <h3 class="card-title">该日摄入分析报告</h3>
            <div class="insights-container">
              <div id="insights-list" class="insights-list">
                <!-- Dynamically populated insight cards -->
              </div>
            </div>
          </section>

          <!-- Companion Chat UI -->
          <div class="chat-container glass" style="padding: 16px; background: rgba(255, 255, 255, 0.6); border-radius: 12px; border: 1px solid rgba(255,255,255,0.8); display: flex; flex-direction: column; height: 300px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); margin-top: 16px;">
            <h3 style="margin-top: 0; margin-bottom: 12px; font-size: 1.1rem; color: #475569; display: flex; align-items: center; gap: 8px;">
              <span>☕</span> 交互小助手
            </h3>
            <div id="chat-history" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding-right: 8px; margin-bottom: 12px;">
              <!-- Messages go here -->
            </div>
            <div style="display: flex; gap: 8px;">
              <input id="chat-input" type="text" placeholder="问我任何问题..." style="flex: 1; padding: 10px 14px; border: 1px solid rgba(0,0,0,0.1); border-radius: 8px; font-family: inherit; font-size: 0.95rem; outline: none; background: rgba(255,255,255,0.8);">
              <button id="chat-send-btn" style="background: linear-gradient(135deg, #a855f7, #c084fc); color: white; border: none; border-radius: 8px; padding: 0 16px; font-weight: 600; cursor: pointer; transition: all 0.2s;">发送</button>
            </div>
          </div>
"""

# Replace the existing insights-section with BOTH insights-section AND chat UI
html = re.sub(
    r'<!-- Dynamic Daily Insights -->\s*<section class="insights-section card glass">.*?</section>',
    chat_html,
    html,
    flags=re.DOTALL
)

with open(dest_html, 'w', encoding='utf-8') as f:
    f.write(html)
