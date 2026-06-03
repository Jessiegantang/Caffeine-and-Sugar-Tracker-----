import os
import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 1. Replace 300ms transitions with 150ms ease-out
css = css.replace('transition: all 0.3s ease;', 'transition: all 0.15s ease-out;')
css = css.replace('transition: background 0.3s ease;', 'transition: background 0.15s ease-out;')
css = css.replace('transition: width 0.5s ease;', 'transition: width 0.2s ease-out;')
css = css.replace('transition: height 0.5s ease;', 'transition: height 0.2s ease-out;')

# 2. Replace gradients with solid colors
css = css.replace('var(--caffeine-gradient)', 'var(--caffeine-primary)')
css = css.replace('var(--sugar-gradient)', 'var(--sugar-primary)')

# 3. Replace custom shadows with tailwind defaults
css = css.replace('box-shadow: 0 4px 15px var(--caffeine-glow);', '')
css = css.replace('box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);', 'box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);')
css = css.replace('box-shadow: 0 4px 15px rgba(124, 183, 158, 0.3);', '')
css = css.replace('box-shadow: 0 4px 15px rgba(232, 150, 150, 0.3);', '')
css = css.replace('box-shadow: 0 0 0 3px var(--caffeine-glow);', 'outline: 2px solid var(--caffeine-primary); outline-offset: 2px;')

# 4. Enforce h-dvh
css = css.replace('min-height: 100vh;', 'min-height: 100dvh;')

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print('style.css restored and updated!')
