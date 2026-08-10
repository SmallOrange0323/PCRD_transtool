import os
import re

dist_dir = "dist_story_map"
dashboard_dir = "dashboard"

index_html_path = os.path.join(dist_dir, "index.html")
db_js_path = os.path.join(dashboard_dir, "db.js")
chapter_data_js_path = os.path.join(dashboard_dir, "chapter-data.js")

with open(db_js_path, 'r', encoding='utf-8') as f:
    db_js_code = f.read()
with open(chapter_data_js_path, 'r', encoding='utf-8') as f:
    chapter_data_js_code = f.read()
with open(index_html_path, 'r', encoding='utf-8') as f:
    html_content = f.read()

# 替換 db.js script tag
html_content = re.sub(
    r'<script src="db\.js(?:\?v=[^"]*)?"></script>',
    lambda m: f'<script>\n// === db.js INLINED ===\n{db_js_code}\n// === END db.js ===\n</script>',
    html_content
)
# 替換 chapter-data.js script tag
html_content = re.sub(
    r'<script src="chapter-data\.js(?:\?v=[^"]*)?"></script>',
    lambda m: f'<script>\n// === chapter-data.js INLINED ===\n{chapter_data_js_code}\n// === END chapter-data.js ===\n</script>',
    html_content
)

with open(index_html_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Inline completed! File size: {os.path.getsize(index_html_path)}")
