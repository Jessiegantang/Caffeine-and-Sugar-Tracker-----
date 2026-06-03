import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
        except:
            continue
        
        if 'tool_calls' in data:
            for call in data['tool_calls']:
                name = call.get('function', {}).get('name', '')
                args = call.get('function', {}).get('arguments', '')
                if 'index.html' in args and ('replace' in name or 'write' in name):
                    print("Step:", data.get('step_index'), "Tool:", name)
                    print("Args:", args[:300], "...")
                    print("-" * 50)
