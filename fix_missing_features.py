import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Merge Weekly stats into Daily
# Find Weekly content
weekly_match = re.search(r'(<section class="weekly-stats-card card glass">.*?</section>\s*<section class="chart-card card glass">.*?</section>)', html, flags=re.DOTALL)
if weekly_match:
    weekly_content = weekly_match.group(1)
    # Remove from tab-weekly
    html = html.replace(weekly_content, '')
    
    # Append to tab-daily (right after the Chat Assistant)
    chat_end = html.find('</div>\n        </div>\n        \n        <!-- ==================== TAB 2: WEEKLY STATISTICS ==================== -->')
    if chat_end != -1:
        # insert weekly_content
        html = html[:chat_end] + '\n' + weekly_content + html[chat_end:]
    
    # Remove tab-weekly button
    html = re.sub(r'<button class="tab-btn" data-tab="tab-weekly">.*?</button>', '', html, flags=re.DOTALL)

# 2. Add the missing DOM elements so Chat History loads!
budget_html = """
          <!-- Daily Budget & Agent Analysis Section -->
          <section class="agent-section card glass" style="border: 2px solid #c084fc; background: rgba(192, 132, 252, 0.05); margin-bottom: 16px;">
            <div class="section-header-row">
              <h3 class="card-title" style="color: #c084fc;">☕ 今日预算与平衡策略</h3>
              <span id="agent-risk-badge" class="badge" style="background: #a855f7; color: white;">分析中...</span>
            </div>
            <div class="agent-container" style="padding-top: 15px;">
              <div style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.9rem;">
                  <span>咖啡因剩余预算</span>
                  <span id="caffeine-budget-text">0 / 400 mg</span>
                </div>
                <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; margin-bottom: 12px;">
                  <div id="caffeine-budget-bar" style="height: 100%; width: 0%; background: #c084fc; transition: width 0.3s ease;"></div>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.9rem;">
                  <span>糖分剩余预算</span>
                  <span id="sugar-budget-text">0 / 50 g</span>
                </div>
                <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden;">
                  <div id="sugar-budget-bar" style="height: 100%; width: 0%; background: #f472b6; transition: width 0.3s ease;"></div>
                </div>
              </div>
              <div id="agent-advice-text" style="font-size: 0.95rem; line-height: 1.5; color: var(--text-secondary);"></div>
            </div>
          </section>
"""

# Insert budget_html above the insights-section
html = html.replace('<!-- Dynamic Daily Insights -->', budget_html + '\n          <!-- Dynamic Daily Insights -->')

# 3. Add Sleep Logging missing DOM
sleep_html = """
          <section class="form-section card glass" style="margin-top: 16px;">
            <h3 class="card-title">睡眠补录</h3>
            <div class="form-group" style="display: flex; gap: 8px; align-items: center;">
              <input type="number" id="input-sleep" class="form-control" placeholder="睡眠时长 (小时)" step="0.5" style="flex: 1;">
              <button id="save-sleep-btn" class="btn btn-primary">保存</button>
            </div>
          </section>
"""
# Insert sleep logging below the "录入新饮品" form in workspace-left
html = html.replace('<!-- ==================== TAB 1: DAILY DASHBOARD ==================== -->', sleep_html + '\n        </div>\n        <!-- ==================== TAB 1: DAILY DASHBOARD ==================== -->')

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
    f.write(html)

