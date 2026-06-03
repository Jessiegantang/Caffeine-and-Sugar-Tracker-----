with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\missing_html_dump.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# I will write the literal unescaped string to a new file so I can read it cleanly
with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\clean_html.html', 'w', encoding='utf-8') as out:
    # content has literal \n from json dumps, let's decode it
    out.write(content.encode('utf-8').decode('unicode_escape'))
