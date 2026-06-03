import re

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

bad_snippet = """            </div>
          </section>

        </div> <!-- Close workspace-grid -->"""

good_snippet = """            </div>
          </section>
        </div> <!-- Close tab-daily -->
      </div> <!-- Close workspace-right -->
        </div> <!-- Close workspace-grid -->"""

if bad_snippet in html:
    html = html.replace(bad_snippet, good_snippet)
    with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Fixed missing closing divs!")
else:
    print("Snippet not found! Trying fallback...")
    bad_snippet_fallback = r'(<section class="weekly-insights-section card glass">.*?</section>)\s*</div> <!-- Close workspace-grid -->'
    match = re.search(bad_snippet_fallback, html, flags=re.DOTALL)
    if match:
        html = html.replace(match.group(0), match.group(1) + '\n        </div>\n      </div>\n        </div> <!-- Close workspace-grid -->')
        with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Fixed missing closing divs with fallback!")
    else:
        print("Fallback also not found.")
