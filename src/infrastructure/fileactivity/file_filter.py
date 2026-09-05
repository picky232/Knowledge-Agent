import os

EXCLUDED_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "Library",
    ".next", "dist", "build", ".cache", "site-packages", ".pytest_cache",
    ".mypy_cache", ".idea", ".vscode", "target", "vendor", ".gradle",
}

TRACKED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".h", ".cpp", ".hpp",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sql", ".sh",
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".scss",
    ".ipynb", ".jsp", ".vue", ".csv",
}


def is_tracked(path: str) -> bool:
    """작업으로 볼 만한 파일만 통과시킨다. 숨김 파일/폴더, 의존성·빌드 산출물,
    확장자 없는 임시 파일은 전부 제외 — 저장 한 번에 수십 개씩 쏟아지는
    캐시 쓰기가 기록을 뒤덮는 것을 막기 위함."""
    parts = path.split(os.sep)

    for part in parts[:-1]:
        if part in EXCLUDED_DIR_NAMES or part.startswith("."):
            return False

    filename = parts[-1]
    if filename.startswith("."):
        return False

    _, ext = os.path.splitext(filename)
    return ext.lower() in TRACKED_EXTENSIONS
