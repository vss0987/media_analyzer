from ui import pick_files
from main import load_titles
from services import load_data, build_result, get_lst, compute_stats, format_stats

files = pick_files() or None        # None → возьмутся FILES по умолчанию
titles = load_titles(files)
data = load_data(files)
result = build_result(data)
result.to_excel("result.xlsx", index=False)
print(format_stats(compute_stats(data)))