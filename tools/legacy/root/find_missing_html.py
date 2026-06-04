import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'agent-risk-badge' in line:
            try:
                data = json.loads(line)
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        args = call.get('args', {})
                        if isinstance(args, str):
                            args = json.loads(args, strict=False)
                        
                        if args.get('TargetFile', '').endswith('index.html'):
                            print("FOUND agent-risk-badge in tool call:")
                            if 'ReplacementContent' in args:
                                print(args['ReplacementContent'])
                            elif 'ReplacementChunks' in args:
                                chunks = json.loads(args['ReplacementChunks'], strict=False) if isinstance(args['ReplacementChunks'], str) else args['ReplacementChunks']
                                for chunk in chunks:
                                    if 'agent-risk-badge' in chunk.get('ReplacementContent', ''):
                                        print(chunk['ReplacementContent'])
            except Exception as e:
                print("Error parsing:", e)

        if 'input-sleep' in line:
            try:
                data = json.loads(line)
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        args = call.get('args', {})
                        if isinstance(args, str):
                            args = json.loads(args, strict=False)
                        
                        if args.get('TargetFile', '').endswith('index.html'):
                            print("FOUND input-sleep in tool call:")
                            if 'ReplacementContent' in args:
                                print(args['ReplacementContent'])
                            elif 'ReplacementChunks' in args:
                                chunks = json.loads(args['ReplacementChunks'], strict=False) if isinstance(args['ReplacementChunks'], str) else args['ReplacementChunks']
                                for chunk in chunks:
                                    if 'input-sleep' in chunk.get('ReplacementContent', ''):
                                        print(chunk['ReplacementContent'])
            except Exception as e:
                pass
