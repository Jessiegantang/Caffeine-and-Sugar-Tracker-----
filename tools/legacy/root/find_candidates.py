import json
import re

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

found_html = ""
found_css = ""

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
        except:
            continue
            
        step = data.get('step_index', 0)
        if step > 2555:
            break
            
        if data.get('type') == 'TOOL_RESPONSE':
            content = data.get('content', '')
            if isinstance(content, str):
                if 'weekly-trends' in content or '交互小助手' in content or 'ChatBox' in content or 'tab-weekly' in content:
                    if '<!DOCTYPE html>' in content:
                        found_html = content
                if 'caffeine-gradient' in content and ':root' in content:
                    found_css = content

if found_html:
    print(f"Found a good HTML candidate of length {len(found_html)}")
    with open('candidate_html.txt', 'w', encoding='utf-8') as f:
        f.write(found_html)
else:
    print("No good HTML candidate found.")

if found_css:
    print(f"Found a good CSS candidate of length {len(found_css)}")
    with open('candidate_css.txt', 'w', encoding='utf-8') as f:
        f.write(found_css)
