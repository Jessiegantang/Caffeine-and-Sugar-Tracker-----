import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('<!-- ==================== TAB 3: DATABASE MANAGEMENT ==================== -->')
print(html[idx-150:idx+50])
