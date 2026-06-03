import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\sleep_lines.txt', 'w', encoding='utf-8') as out:
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if 'input-sleep' in line:
                try:
                    data = json.loads(line)
                    # write formatted json
                    out.write(f"--- STEP {data.get('step_index')} ---\n")
                    out.write(json.dumps(data, indent=2, ensure_ascii=False))
                    out.write("\n\n")
                except:
                    pass
