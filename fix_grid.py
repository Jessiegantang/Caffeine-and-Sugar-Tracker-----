import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

bad_snippet = """      </div>

      <!-- Right Column: Tabs Contents -->
      <div class="workspace-right">
        
        
          <section class="form-section card glass" style="margin-top: 16px;">
            <h3 class="card-title">睡眠补录</h3>
            <div class="form-group" style="display: flex; gap: 8px; align-items: center;">
              <input type="number" id="input-sleep" class="form-control" placeholder="睡眠时长 (小时)" step="0.5" style="flex: 1;">
              <button id="save-sleep-btn" class="btn btn-primary">保存</button>
            </div>
          </section>

        </div>
        <!-- ==================== TAB 1: DAILY DASHBOARD ==================== -->"""

good_snippet = """          <section class="form-section card glass" style="margin-top: 16px;">
            <h3 class="card-title">睡眠补录</h3>
            <div class="form-group" style="display: flex; gap: 8px; align-items: center;">
              <input type="number" id="input-sleep" class="form-control" placeholder="睡眠时长 (小时)" step="0.5" style="flex: 1;">
              <button id="save-sleep-btn" class="btn btn-primary">保存</button>
            </div>
          </section>
      </div>

      <!-- Right Column: Tabs Contents -->
      <div class="workspace-right">
        <!-- ==================== TAB 1: DAILY DASHBOARD ==================== -->"""

if bad_snippet in html:
    html = html.replace(bad_snippet, good_snippet)
    with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Fixed layout bug!")
else:
    print("Snippet not found!")
