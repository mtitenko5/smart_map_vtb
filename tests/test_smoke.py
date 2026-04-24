from pathlib import Path
import py_compile


BASE_DIR = Path(__file__).resolve().parents[1]


def test_python_files_compile():
    for filename in ["app.py", "logic.py", "styles.py"]:
        py_compile.compile(str(BASE_DIR / filename), doraise=True)