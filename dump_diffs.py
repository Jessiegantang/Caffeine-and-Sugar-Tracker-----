import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

diffs = []
with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'index.html' in line and 'ReplacementChunks' in line:
            try:
                data = json.loads(line)
            except:
                continue
            
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    args = call.get('function', {}).get('arguments', '')
                    if isinstance(args, str) and 'index.html' in args:
                        diffs.append(args)
                        
with open('diffs.txt', 'w', encoding='utf-8') as out:
    for d in diffs:
        out.write(d + "\n\n")

print(f"Dumped {len(diffs)} diffs.")
