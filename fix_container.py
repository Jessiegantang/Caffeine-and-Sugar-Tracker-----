import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Change app-container to container
html = html.replace('class="app-container"', 'class="container"')

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
    f.write(html)
