import re

html_path = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Remove the weekly tab button
html = re.sub(
    r'<button class="tab-btn" data-tab="tab-weekly">.*?</button>',
    '',
    html,
    flags=re.DOTALL
)

# Find the content of tab-weekly
weekly_match = re.search(r'<!-- ==================== TAB 2: WEEKLY STATISTICS ==================== -->(.*?)<!-- ==================== TAB 3: DATABASE MANAGEMENT ==================== -->', html, flags=re.DOTALL)
if weekly_match:
    weekly_content = weekly_match.group(1)
    
    # Remove the wrapper div <div id="tab-weekly" class="tab-content"> and its closing tag
    weekly_content = re.sub(r'<div id="tab-weekly" class="tab-content">', '', weekly_content)
    # The closing tag is right before the Tab 3 comment
    weekly_content = weekly_content.rsplit('</div>', 1)[0]
    
    # We want to append this content into tab-daily
    # Let's find where tab-daily ends
    html = re.sub(
        r'(<!-- Companion Chat UI -->.*?</div>\s*</div>)',
        r'\1\n' + weekly_content,
        html,
        flags=re.DOTALL
    )

    # Remove the old tab-weekly block completely
    html = html.replace(weekly_match.group(0), '<!-- ==================== TAB 3: DATABASE MANAGEMENT ==================== -->')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)
