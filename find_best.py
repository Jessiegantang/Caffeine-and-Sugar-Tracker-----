import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

best_html = ""
best_css = ""

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
        except:
            continue
            
        step = data.get('step_index', 0)
        if step >= 2554:
            break
            
        # Search for full file contents in TOOL_RESPONSE
        if data.get('type') == 'TOOL_RESPONSE':
            content = data.get('content', '')
            if isinstance(content, str):
                if '<!DOCTYPE html>' in content and '<!-- ==================== TAB 2: WEEKLY STATISTICS ==================== -->' in content:
                    best_html = content
                if '--bg-deep' in content and 'linear-gradient' in content and ':root' in content:
                    best_css = content

print("HTML length:", len(best_html))
print("CSS length:", len(best_css))

if best_html:
    with open('best_html.txt', 'w', encoding='utf-8') as f:
        f.write(best_html)
if best_css:
    with open('best_css.txt', 'w', encoding='utf-8') as f:
        f.write(best_css)
