import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        if 'chat-container glass' in line and 'ReplacementChunks' in line:
            try:
                data = json.loads(line)
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        args = call.get('function', {}).get('arguments', '')
                        if 'chat-container glass' in args:
                            args_json = json.loads(args)
                            chunks = json.loads(args_json['ReplacementChunks'])
                            for chunk in chunks:
                                if 'chat-container glass' in chunk.get('ReplacementContent', ''):
                                    with open('chat_html_diff.txt', 'w', encoding='utf-8') as out:
                                        out.write(chunk['ReplacementContent'])
                                    print("Saved chat_html_diff.txt")
            except:
                pass
