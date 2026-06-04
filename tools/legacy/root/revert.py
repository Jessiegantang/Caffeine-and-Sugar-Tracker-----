import shutil
import os

src_dir = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker'
dest_dir = r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份'

# Restore index.html
shutil.copy2(os.path.join(src_dir, 'index.html'), os.path.join(dest_dir, 'index.html'))

# Restore style.css
shutil.copy2(os.path.join(src_dir, 'style.css'), os.path.join(dest_dir, 'style.css'))

# Remove aria-label from main.js
main_js_path = os.path.join(dest_dir, 'main.js')
with open(main_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(' aria-label="删除记录"', '')

with open(main_js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Reverted all changes successfully!')
