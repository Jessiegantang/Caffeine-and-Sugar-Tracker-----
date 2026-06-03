import os
import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Apply baseline-ui fixes to HTML
# 1. Inject Tailwind CDN and config
tailwind_script = '''  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'system-ui', 'sans-serif'],
          }
        }
      }
    }
  </script>'''
html = html.replace('<link rel="stylesheet" href="/style.css">', tailwind_script + '\n  <link rel="stylesheet" href="/style.css">')

# 2. Add text-balance to headings and tabular-nums
html = html.replace('<div class="app-container">', '<div class="app-container font-sans text-pretty">')
html = html.replace('<h1>Caffeine and Sugar</h1>', '<h1 class="text-balance tabular-nums">Caffeine and Sugar</h1>')
html = html.replace('<p class="subtitle">', '<p class="subtitle text-pretty">轻量级饮品摄入追踪与健康分析看板</p>') # make sure text matches

html = re.sub(r'class="card-title"', 'class="card-title text-balance"', html)
html = re.sub(r'class="section-title"', 'class="section-title text-balance"', html)
html = re.sub(r'class="stat-value"', 'class="stat-value tabular-nums"', html)
html = re.sub(r'class="agg-val([^"]*)"', r'class="agg-val\1 tabular-nums"', html)
html = re.sub(r'class="log-item-value([^"]*)"', r'class="log-item-value\1 tabular-nums"', html)
html = re.sub(r'class="db-stat-value"', 'class="db-stat-value tabular-nums"', html)

# 3. Add aria-labels
html = html.replace('<button type="button" id="drink-search-btn">', '<button type="button" id="drink-search-btn" aria-label="搜索饮品">')
html = html.replace('<button type="button" id="import-modal-close" class="modal-close-btn">', '<button type="button" id="import-modal-close" class="modal-close-btn" aria-label="关闭导入弹窗">')
html = html.replace('<button type="button" id="modal-close-btn" class="modal-close-btn">', '<button type="button" id="modal-close-btn" class="modal-close-btn" aria-label="关闭编辑弹窗">')

# 4. Remove blur-glow shapes
html = re.sub(r'<div class="blur-glow shape-[12]"></div>\n?', '', html)

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('index.html restored and updated!')
