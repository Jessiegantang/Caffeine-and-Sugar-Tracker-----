import os

appdata = os.path.expandvars(r'%APPDATA%')
print(f"Searching in {appdata}")

candidates = []

for root, dirs, files in os.walk(appdata):
    if 'History' in root:
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
    import shutil
    shutil.copy2(best, r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\recovered_index.html')
    print("Recovered!")
else:
    print("Not found in any History folder.")
