import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

found_html = False
with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\missing_html_dump.txt', 'w', encoding='utf-8') as out:
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            if ('agent-risk-badge' in line or 'save-sleep-btn' in line) and 'replace_file_content' in line:
                try:
                    data = json.loads(line)
                    if 'tool_calls' in data:
                        for call in data['tool_calls']:
                            args = call.get('args', {})
                            if isinstance(args, str):
                                args = json.loads(args, strict=False)
                            
                            if 'index.html' in args.get('TargetFile', ''):
                                if 'ReplacementContent' in args:
                                    out.write(f"--- STEP {data.get('step_index')} ---\n")
                                    out.write(args['ReplacementContent'] + '\n\n')
                                elif 'ReplacementChunks' in args:
                                    chunks = args['ReplacementChunks']
                                    if isinstance(chunks, str):
                                        chunks = json.loads(chunks, strict=False)
                                    for chunk in chunks:
                                        if 'agent-risk-badge' in chunk.get('ReplacementContent', '') or 'save-sleep-btn' in chunk.get('ReplacementContent', ''):
                                            out.write(f"--- STEP {data.get('step_index')} CHUNK ---\n")
                                            out.write(chunk['ReplacementContent'] + '\n\n')
                except Exception as e:
                    pass
