import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

idx = html.find('workspace-left')
end_idx = html.find('tab-daily', idx)
print(html[idx:end_idx + 100])
