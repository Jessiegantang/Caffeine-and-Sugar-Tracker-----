import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Make the grid 1fr 1fr for symmetry
css = re.sub(r'grid-template-columns:\s*350px\s*1fr;', 'grid-template-columns: 1fr 1fr;', css)

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'w', encoding='utf-8') as f:
    f.write(css)
