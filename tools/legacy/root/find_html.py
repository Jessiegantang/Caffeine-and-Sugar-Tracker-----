import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'index.html' in line:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    print('Tool Call at step:', data.get('step_index'), call.get('function', {}).get('name'))
            if data.get('type') == 'TOOL_RESPONSE':
                print('Tool Response at step:', data.get('step_index'))
