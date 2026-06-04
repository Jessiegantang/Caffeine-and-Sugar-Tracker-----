import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

expected_ids = [
    'agent-risk-badge', 'caffeine-budget-bar', 'caffeine-budget-text',
    'caffeine-progress', 'caffeine-total', 'chat-history', 'chat-input',
    'chat-send-btn', 'db-custom-count', 'db-total-count', 'drinks-table-body',
    'edit-drink-abv', 'edit-drink-brand', 'edit-drink-caffeine', 'edit-drink-id',
    'edit-drink-name', 'edit-drink-sugar', 'edit-drink-volume', 'input-sleep',
    'main-content', 'new-drink-abv', 'new-drink-brand', 'new-drink-caffeine',
    'new-drink-name', 'new-drink-sugar', 'new-drink-volume', 'save-sleep-btn',
    'sugar-budget-bar', 'sugar-budget-text', 'sugar-progress', 'sugar-total',
    'tab-database', 'workspace-left'
]

missing = []
for expected in expected_ids:
    if f'id="{expected}"' not in html:
        missing.append(expected)

print("Missing IDs:", missing)
