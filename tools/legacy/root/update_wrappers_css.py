import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Update .container
css = re.sub(r'\.container\s*{[^}]*}', r'.container {\n  width: 100%;\n  max-width: 1200px;\n  margin: 0 auto;\n  position: relative;\n  z-index: 1;\n}', css)

# Update .main-content
css = re.sub(r'\.main-content\s*{[^}]*}', r'.main-content {\n  width: 100%;\n  max-width: 1200px;\n  margin: 0 auto;\n}', css)

# Update .database-full-width
css = re.sub(r'\.database-full-width\s*{[^}]*}', r'.database-full-width {\n  position: relative;\n  width: 100%;\n  max-width: 1200px;\n  margin: 0 auto;\n  padding: 0;\n}', css)

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'w', encoding='utf-8') as f:
    f.write(css)
print("Updated CSS wrappers successfully!")
