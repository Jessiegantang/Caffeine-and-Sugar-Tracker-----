import json

transcript_path = r'C:\Users\jessie\.gemini\antigravity\brain\c053404e-8ca4-4bff-a26e-62449b65b517\.system_generated\logs\transcript.jsonl'

latest_html = None
latest_css = None

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        step = data.get('step_index', 0)
        
        # Stop before the baseline-ui modifications (step 2558)
        if step > 2555:
            break
            
        if data.get('type') == 'TOOL_RESPONSE' and 'index.html' in data.get('content', ''):
            if '<!DOCTYPE html>' in data.get('content', ''):
                latest_html = data.get('content')
                
        if data.get('type') == 'TOOL_RESPONSE' and 'style.css' in data.get('content', ''):
            if ':root' in data.get('content', ''):
                latest_css = data.get('content')

if latest_html:
    # clean the view_file line numbers
    lines = latest_html.split('\n')
    cleaned_lines = []
    in_file = False
    for line in lines:
        if line.startswith('1: '):
            in_file = True
        if line.startswith('The above content does NOT show') or line.startswith('The above content shows the entire'):
            in_file = False
        if in_file:
            # remove line number prefix like "123: "
            if ': ' in line:
                cleaned_lines.append(line.split(': ', 1)[1])
            else:
                cleaned_lines.append(line)
    
    # We might not have the FULL file if it was truncated in view_file.
    # Let's print the length
    print(f"Extracted index.html (Lines: {len(cleaned_lines)})")
    
    with open('extracted_index.html', 'w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned_lines))
