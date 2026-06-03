import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'chat-history' in line:
            try:
                data = json.loads(line)
                print("Found chat-history at step:", data.get('step_index'))
            except:
                pass
