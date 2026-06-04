import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

found = False
with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
        except:
            continue
            
        if '周度趋势与分析' in line or '交互小助手' in line:
            print("Found in step:", data.get('step_index', 0))
            if 'tool_calls' in data:
                print("Tool call:", data['tool_calls'][0]['function']['name'])
            elif data.get('type') == 'TOOL_RESPONSE':
                content = data.get('content', '')
                if isinstance(content, str) and '<!DOCTYPE html>' in content:
                    with open('found_html.txt', 'w', encoding='utf-8') as out:
                        out.write(content)
                    print("Saved found_html.txt")
                    found = True
                    break
