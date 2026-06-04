import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Look for inline styles with negative margins
neg_margins = re.findall(r'style="[^"]*margin[^"]*-[0-9]+[^"]*"', html)
print("Negative margins in HTML:", neg_margins)

# Look for items-start
items_start = re.findall(r'class="[^"]*items-start[^"]*"', html)
print("items-start classes in HTML:", items_start)

# Look for flex classes on wrappers
wrapper_classes = re.findall(r'class="(container|main-content|tab-content-wrapper|database-full-width)[^"]*"', html)
print("Wrapper classes:", wrapper_classes)
