import json
import os

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

lines_with_html = []
with open(transcript_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if 'chat-container glass' in line and '<!-- Companion Chat UI -->' in line:
            lines_with_html.append(line)

print(f"Found {len(lines_with_html)} lines with chat container.")

for idx, line in enumerate(lines_with_html[-1:]): # Just look at the last one
    try:
        data = json.loads(line)
        if 'tool_calls' in data:
            for call in data['tool_calls']:
                args = call.get('args', {})
                if isinstance(args, str):
                    args = json.loads(args, strict=False)
                
                if args.get('TargetFile', '').endswith('index.html'):
                    content = args.get('CodeContent', '')
                    if content:
                        with open(f'dumped_html_final.html', 'w', encoding='utf-8') as out:
                            out.write(content)
                        print("Dumped full HTML!")
                    else:
                        print("No CodeContent, just replacement chunks.")
    except Exception as e:
        print("Error:", e)
