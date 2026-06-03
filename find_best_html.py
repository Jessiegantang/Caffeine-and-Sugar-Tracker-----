import json
import re

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

best_html = ""
max_len = 0

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        content = data.get('content', '')
        if isinstance(content, str) and '<!DOCTYPE html>' in content:
            # check if it's the full file
            if '</html>' in content and len(content) > max_len:
                max_len = len(content)
                best_html = content

if best_html:
    print(f"Found HTML of length {max_len}")
    
    # Strip tool prefix
    lines = best_html.split('\n')
    cleaned = []
    in_file = False
    for line in lines:
        if line.startswith('1: <!DOCTYPE html>'):
            in_file = True
        
        if in_file:
            if line.startswith('The above content'):
                break
            # Remove line number prefix "123: "
            if re.match(r'^\d+: ', line):
                cleaned.append(line.split(': ', 1)[1])
            else:
                cleaned.append(line)
                
    with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\recovered_index.html', 'w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned))
    print(f"Recovered HTML saved. Lines: {len(cleaned)}")
else:
    print("No valid HTML found in transcript.")
