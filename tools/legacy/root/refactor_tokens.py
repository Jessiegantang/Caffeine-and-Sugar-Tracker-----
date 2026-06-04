import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 1. Mapping old variables to new component/semantic variables
var_map = {
    'var(--bg-deep)': 'var(--app-bg)',
    'var(--bg-card)': 'var(--card-bg)',
    'var(--border-color)': 'var(--color-border-subtle)',
    'var(--border-hover)': 'var(--color-border-strong)',
    'var(--text-primary)': 'var(--app-text)',
    'var(--text-secondary)': 'var(--color-text-muted)',
    'var(--text-muted)': 'var(--color-text-disabled)',
    'var(--caffeine-primary)': 'var(--color-brand-primary)',
    'var(--sugar-primary)': 'var(--color-brand-secondary)',
    'var(--color-success)': 'var(--color-state-success)',
    'var(--color-success-bg)': 'var(--color-state-success-bg)',
    'var(--color-warning)': 'var(--color-state-warning)',
    'var(--color-warning-bg)': 'var(--color-state-warning-bg)',
    'var(--color-danger)': 'var(--color-state-danger)',
    'var(--color-danger-bg)': 'var(--color-state-danger-bg)',
    'var(--color-info)': 'var(--color-state-info)',
    'var(--color-info-bg)': 'var(--color-state-info-bg)'
}

# 2. Replace usages in the body of the CSS
# We'll split the css to avoid replacing inside :root
parts = css.split('}', 1)
if len(parts) == 2:
    root_block, body_block = parts
    
    for old, new in var_map.items():
        body_block = body_block.replace(old, new)
        
    # Replace any stray hex colors in body block
    # Actually it's safer to leave them or replace specific known ones
    # The prompt says: "Never use raw hex in components - always reference tokens"
    # Let's find any #hex in the body
    body_block = body_block.replace('color: white;', 'color: var(--color-white);')
    body_block = body_block.replace('background: transparent;', 'background: var(--color-transparent);')
    body_block = body_block.replace('border: none;', 'border: none; /* Uses default or transparent */')
    body_block = body_block.replace('border: 1px solid transparent;', 'border: 1px solid var(--color-transparent);')
    
    # 3. Create the new :root block
    new_root = """:root {
  /* =========================================
     PRIMITIVE LAYER (Raw Values)
     ========================================= */
  --color-stone-50: #fdf8f6;
  --color-stone-100: #e8e4e1;
  --color-stone-200: #d4cfcb;
  --color-stone-500: #9a9590;
  --color-stone-600: #6b6560;
  --color-stone-900: #2d2926;
  --color-white: #ffffff;
  --color-amber-500: #d4a574;
  --color-amber-600: #c49a6c;
  --color-amber-500-alpha-10: rgba(212, 165, 116, 0.1);
  --color-amber-500-alpha-8: rgba(212, 165, 116, 0.08);
  --color-rose-300: #ffb3c1;
  --color-emerald-400: #7cb79e;
  --color-emerald-400-alpha-15: rgba(124, 183, 158, 0.15);
  --color-emerald-400-alpha-30: rgba(124, 183, 158, 0.3);
  --color-yellow-400: #e5c178;
  --color-yellow-400-alpha-15: rgba(229, 193, 120, 0.15);
  --color-red-400: #e89696;
  --color-red-400-alpha-15: rgba(232, 150, 150, 0.15);
  --color-red-400-alpha-30: rgba(232, 150, 150, 0.3);
  --color-blue-400: #8eb8db;
  --color-blue-400-alpha-15: rgba(142, 184, 219, 0.15);
  --color-transparent: transparent;
  
  --font-sans: 'Inter', 'Noto Sans SC', system-ui, -apple-system, sans-serif;

  /* =========================================
     SEMANTIC LAYER (Purpose Aliases)
     ========================================= */
  --color-bg-app: var(--color-stone-50);
  --color-bg-surface: var(--color-white);
  --color-text-main: var(--color-stone-900);
  --color-text-muted: var(--color-stone-600);
  --color-text-disabled: var(--color-stone-500);
  --color-border-subtle: var(--color-stone-100);
  --color-border-strong: var(--color-stone-200);
  
  --color-brand-primary: var(--color-amber-500);
  --color-brand-primary-hover: var(--color-amber-600);
  --color-brand-primary-alpha-10: var(--color-amber-500-alpha-10);
  --color-brand-primary-alpha-8: var(--color-amber-500-alpha-8);
  
  --color-brand-secondary: var(--color-rose-300);
  
  --color-state-success: var(--color-emerald-400);
  --color-state-success-bg: var(--color-emerald-400-alpha-15);
  --color-state-warning: var(--color-yellow-400);
  --color-state-warning-bg: var(--color-yellow-400-alpha-15);
  --color-state-danger: var(--color-red-400);
  --color-state-danger-bg: var(--color-red-400-alpha-15);
  --color-state-info: var(--color-blue-400);
  --color-state-info-bg: var(--color-blue-400-alpha-15);

  /* =========================================
     COMPONENT LAYER (Component-Specific)
     ========================================= */
  --app-bg: var(--color-bg-app);
  --app-text: var(--color-text-main);
  
  --card-bg: var(--color-bg-surface);
  --card-border: var(--color-border-subtle);
  
  --btn-primary-bg: var(--color-brand-primary);
  --btn-primary-text: var(--color-white);
  
  --btn-success-bg: var(--color-state-success);
  --btn-success-text: var(--color-white);
  
  --btn-danger-bg: var(--color-state-danger);
  --btn-danger-text: var(--color-white);
  
  --input-bg: var(--color-bg-app);
  --input-border: var(--color-border-subtle);
  --input-focus-border: var(--color-brand-primary);
  
  --tab-bg: var(--color-bg-surface);
  --tab-text: var(--color-text-muted);
  --tab-hover-bg: var(--color-brand-primary-alpha-8);
  --tab-active-bg: var(--color-brand-primary);
  --tab-active-text: var(--color-white);
  
  --calendar-hover-bg: var(--color-brand-primary-alpha-10);
  --list-item-hover-bg: var(--color-brand-primary-alpha-8);
"""
    
    # Let's fix specific hardcoded rgba in body
    body_block = body_block.replace('rgba(212, 165, 116, 0.08)', 'var(--list-item-hover-bg)')
    body_block = body_block.replace('rgba(212, 165, 116, 0.1)', 'var(--calendar-hover-bg)')
    
    css = new_root + body_block

    with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\style.css', 'w', encoding='utf-8') as f:
        f.write(css)
    
    print('Tokens refactored successfully.')
else:
    print('Error: Could not parse CSS.')
