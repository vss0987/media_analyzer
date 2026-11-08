from ui import pick_files
from app.main import load_titles
from app.services import load_data, build_result, compute_stats, format_stats

files = pick_files() or None
titles = load_titles(files)
data = load_data(files)
result = build_result(data)
result.to_excel("result.xlsx", index=False)
print(format_stats(compute_stats(data)))