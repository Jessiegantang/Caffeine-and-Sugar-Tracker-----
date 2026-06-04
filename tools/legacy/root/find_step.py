import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

baseline_step = 0
with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'baseline-ui/SKILL.md' in line and '顶级 UI 设计' in line:
            try:
                data = json.loads(line)
                baseline_step = data.get('step_index')
                print("Baseline UI request at step:", baseline_step)
                break
            except:
                pass
