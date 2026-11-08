from tkinter import Tk, filedialog

def pick_files() -> list[str]:
    """Открывает диалог выбора файлов, возвращает список путей."""
    root = Tk()
    root.withdraw()
    paths = filedialog.askopenfilenames(
        title="Выберите Excel-файлы со скачиваниями",
        filetypes=[("Excel", "*.xlsx *.xls"), ("Все файлы", "*.*")],
    )
    root.destroy()
    return list(paths)