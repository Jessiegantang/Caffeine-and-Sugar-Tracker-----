import re
import time

filepath = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html'

with open(filepath, 'r', encoding='utf-8') as f:
    html = f.read()

# Add a cache buster to the stylesheet link
version = int(time.time())
html = re.sub(r'href="/style.css[^"]*"', f'href="/style.css?v={version}"', html)
html = re.sub(r'href="style.css[^"]*"', f'href="style.css?v={version}"', html)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(html)
