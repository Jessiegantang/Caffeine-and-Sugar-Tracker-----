import re

filepath = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html'

with open(filepath, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Move logs-section
logs_match = re.search(r'(<section class="logs-section card glass">.*?</section>)', html, flags=re.DOTALL)
if logs_match:
    logs_content = logs_match.group(1)
    html = html.replace(logs_content, '')
    # Insert at the bottom of workspace-left
    # workspace-left closes right before <div class="workspace-right">
    # Wait, earlier I found:
    #      </div>
    #
    #      <!-- Right Column: Tabs Contents -->
    #      <div class="workspace-right">
    # Let's insert before the last </div> of workspace-left
    insert_pos = html.find('      </div>\n\n      <!-- Right Column: Tabs Contents -->')
    if insert_pos != -1:
        html = html[:insert_pos] + '\n' + logs_content + '\n' + html[insert_pos:]
        print("Moved logs-section")
    else:
        print("Could not find insert pos for logs-section")

# 2. Merge tab-weekly into tab-daily
# The content is from <div id="tab-weekly" class="tab-content"> up to the next </div> that closes it.
weekly_start = html.find('<div id="tab-weekly" class="tab-content">')
if weekly_start != -1:
    # find the next closing div after weekly_start that's not nested
    # Since we know tab-weekly contains <section>s, we can just grab everything between the div and the end of file (or its closing div)
    # Actually, we can use regex to find all <section> inside it
    tab_weekly_match = re.search(r'<div id="tab-weekly" class="tab-content">(.*?)</div>\n\n    </div>\n\n  </div>', html, flags=re.DOTALL)
    if tab_weekly_match:
        weekly_content = tab_weekly_match.group(1)
        # remove the entire tab-weekly div
        html = html.replace(tab_weekly_match.group(0), '</div>\n\n  </div>')
        
        # append weekly_content to tab-daily
        # tab-daily closes before tab-weekly started
        # let's just insert it right before the </div> that closes tab-daily
        tab_daily_end = html.find('</div>\n\n        <!-- ==================== TAB 2: WEEKLY STATISTICS ==================== -->')
        if tab_daily_end == -1:
            tab_daily_end = html.find('</div>\n\n        <!-- ==================== TAB 2:')
            
        if tab_daily_end != -1:
            html = html[:tab_daily_end] + weekly_content + '\n' + html[tab_daily_end:]
            print("Merged tab-weekly")
        else:
            print("Could not find end of tab-daily")
    else:
        # Fallback regex for tab-weekly
        tab_weekly_fallback = re.search(r'<div id="tab-weekly" class="tab-content">(.*?)\s*</div>\s*</div>\s*<!--', html, flags=re.DOTALL)
        if tab_weekly_fallback:
            weekly_content = tab_weekly_fallback.group(1)
            html = html.replace(tab_weekly_fallback.group(0), '</div>\n      <!--')
            # insert at end of tab_daily
            tab_daily_match = re.search(r'(<div id="tab-daily".*?)(</div>\s*<!-- ==================== TAB 2)', html, flags=re.DOTALL)
            if tab_daily_match:
                html = html.replace(tab_daily_match.group(2), weekly_content + '\n' + tab_daily_match.group(2))
                print("Merged tab-weekly using fallback")

# 3. Remove tab-weekly button
html = re.sub(r'<button class="tab-btn" data-tab="tab-weekly">\s*<svg.*?</svg>\s*周度趋势与分析\s*</button>', '', html, flags=re.DOTALL)
print("Removed tab-weekly button")

# 4. Increase Chat Assistant height
html = html.replace('height: 300px;', 'height: 550px;')
print("Increased chat assistant height")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(html)
