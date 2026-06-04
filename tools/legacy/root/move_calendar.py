import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the calendar section
calendar_match = re.search(r'(<section class="calendar-section card glass">.*?</section>\s*)', html, flags=re.DOTALL)
if calendar_match:
    calendar_html = calendar_match.group(1)
    # Remove from original location
    html = html.replace(calendar_html, '')
    
    # Insert at the top of workspace-left
    html = html.replace('<div class="workspace-left" id="workspace-left">', f'<div class="workspace-left" id="workspace-left">\n{calendar_html}')

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
    f.write(html)
