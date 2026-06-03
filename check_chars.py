with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'rb') as f:
    content = f.read()
    
idx = content.find(b'.container')
print(content[idx-20:idx+50])
