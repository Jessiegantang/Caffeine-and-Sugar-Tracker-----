import os
import time

def search_history(base_path):
    print(f"Searching {base_path}...")
    if not os.path.exists(base_path):
        return
    candidates = []
    for root, _, files in os.walk(base_path):
        for f in files:
            if f == 'entries.json':
                continue
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    if 'chat-history' in content and 'insights-list' in content and '<!DOCTYPE html>' in content:
                        candidates.append((path, os.path.getmtime(path)))
            except:
                pass
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        print("Found candidates in", base_path)
        for c in candidates[:3]:
            print(" -", c[0], time.ctime(c[1]))
        import shutil
        shutil.copy2(candidates[0][0], r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\history_index.html')
        print("Copied the latest one to history_index.html")

search_history(os.path.expandvars(r'%APPDATA%\Code\User\History'))
search_history(os.path.expandvars(r'%APPDATA%\Cursor\User\History'))
