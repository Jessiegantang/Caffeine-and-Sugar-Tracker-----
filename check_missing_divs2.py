import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('<!-- Close workspace-grid -->')
print(html[idx-300:idx+50])
