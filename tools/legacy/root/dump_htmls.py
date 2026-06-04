import json
import re

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

count = 0
with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if '<!DOCTYPE html>' in line:
            try:
                data = json.loads(line)
            except:
                continue
            
            content = ""
            if data.get('type') == 'TOOL_RESPONSE':
                content = data.get('content', '')
            elif 'tool_calls' in data:
                # Extract arguments from tool calls
                for call in data['tool_calls']:
                    args = call.get('function', {}).get('arguments', '')
                    if isinstance(args, str) and '<!DOCTYPE html>' in args:
                        content = args
            
            if isinstance(content, str) and '<!DOCTYPE html>' in content:
                count += 1
                with open(f'html_backup_{count}.txt', 'w', encoding='utf-8') as out:
                    out.write(content)

print(f"Dumped {count} HTML backups.")
