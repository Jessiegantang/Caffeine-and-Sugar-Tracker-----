import re
import glob
import os

ids = set()
for fpath in ['main.js', 'src/components/ChatBox.js', 'src/components/DatabasePanel.js']:
    if os.path.exists(fpath):
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
            matches = re.findall(r"getElementById\(['\"](.*?)['\"]\)", content)
            ids.update(matches)
            matches2 = re.findall(r"querySelector\(['\"]#(.*?)['\"]\)", content)
            ids.update(matches2)

for i in sorted(list(ids)):
    print(i)
