import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

def apply_chunks(content, chunks):
    for chunk in chunks:
        target = chunk['TargetContent']
        repl = chunk['ReplacementContent']
        if target in content:
            content = content.replace(target, repl)
        else:
            print("WARNING: Target not found!")
    return content

applied_count = 0

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
        except:
            continue
            
        step = data.get('step_index', 0)
        if step >= 2554:
            break
            
        if 'tool_calls' in data:
            for call in data['tool_calls']:
                name = call.get('name', '')
                args = call.get('args', {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args, strict=False)
                    except:
                        continue
                
                target_file = args.get('TargetFile', '')
                
                if 'index.html' in target_file:
                    if name == 'write_to_file':
                        html = args['CodeContent']
                        applied_count += 1
                    elif name == 'replace_file_content':
                        if args['TargetContent'] in html:
                            html = html.replace(args['TargetContent'], args['ReplacementContent'])
                            applied_count += 1
                        else:
                            print("Target not found in index.html for replace_file_content at step", step)
                    elif name == 'multi_replace_file_content':
                        try:
                            chunks = json.loads(args['ReplacementChunks'], strict=False) if isinstance(args['ReplacementChunks'], str) else args['ReplacementChunks']
                            html = apply_chunks(html, chunks)
                            applied_count += 1
                        except Exception as e:
                            print("Error applying chunks:", e)
                            
                elif 'style.css' in target_file:
                    if name == 'write_to_file':
                        css = args['CodeContent']
                        applied_count += 1
                    elif name == 'replace_file_content':
                        if args['TargetContent'] in css:
                            css = css.replace(args['TargetContent'], args['ReplacementContent'])
                            applied_count += 1
                        else:
                            print("Target not found in style.css for replace_file_content at step", step)
                    elif name == 'multi_replace_file_content':
                        try:
                            chunks = json.loads(args['ReplacementChunks'], strict=False) if isinstance(args['ReplacementChunks'], str) else args['ReplacementChunks']
                            css = apply_chunks(css, chunks)
                            applied_count += 1
                        except Exception as e:
                            print("Error applying chunks CSS:", e)

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index_restored.html', 'w', encoding='utf-8') as f:
    f.write(html)
with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style_restored.css', 'w', encoding='utf-8') as f:
    f.write(css)

print(f"Restoration complete! Applied {applied_count} edits.")
