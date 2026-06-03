import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Count open and close braces before .container
idx = css.find('.container {')
if idx != -1:
    before = css[:idx]
    open_braces = before.count('{')
    close_braces = before.count('}')
    print(f"Before .container: Open braces: {open_braces}, Close braces: {close_braces}")
else:
    print(".container not found")
