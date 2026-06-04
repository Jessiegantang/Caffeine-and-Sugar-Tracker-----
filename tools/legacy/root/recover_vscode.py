import os
import glob
from pathlib import Path

history_dir = os.path.expandvars(r'%APPDATA%\Code\User\History')
print(f"Searching in {history_dir}")

candidates = []

for root, _, files in os.walk(history_dir):
    for file in files:
        if file == 'entries.json':
            continue
        filepath = os.path.join(root, file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if '<title>咖啡因与糖分追踪</title>' in content and 'tab-weekly' in content:
                    candidates.append((filepath, os.path.getmtime(filepath)))
        except:
            pass

if candidates:
    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0][0]
    print(f"Best candidate: {best}")
    with open(best, 'r', encoding='utf-8') as f:
        print("First 20 lines of best candidate:")
        print('\n'.join(f.read().split('\n')[:20]))
    
    import shutil
    shutil.copy2(best, r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\recovered_from_vscode_index.html')
    print("Recovered!")
else:
    print("Not found in VSCode history.")
