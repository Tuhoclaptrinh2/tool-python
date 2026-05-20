import os
import zipfile
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
BACKUP_DIR = PROJECT_DIR / "backup"

EXCLUDE_DIRS = {"__pycache__", "venv", ".venv", "node_modules", ".git", "backup", "images"}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo"}
INCLUDE_EXTENSIONS = {".py", ".txt", ".json", ".md", ".ui", ".yml", ".yaml", ".cfg", ".ini", ".html", ".css", ".js"}


def _should_include(filepath):
    path = Path(filepath)
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False
    if path.suffix in EXCLUDE_EXTENSIONS:
        return False
    return True


def backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{timestamp}.zip"
    zip_path = BACKUP_DIR / filename

    files_added = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                filepath = Path(root) / file
                if not _should_include(filepath):
                    continue

                arcname = filepath.relative_to(PROJECT_DIR)
                zf.write(filepath, arcname)
                files_added += 1

    print(f"Backup created: {filename}")
    print(f"Files included: {files_added}")
    return str(zip_path)


def restore():
    if not BACKUP_DIR.exists():
        print("No backup folder found.")
        return

    zip_files = sorted(BACKUP_DIR.glob("backup_*.zip"))
    if not zip_files:
        print("No backups available.")
        return

    print("\nAvailable backups:")
    for i, zf in enumerate(zip_files, 1):
        stat = zf.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = stat.st_size / 1024
        print(f"  [{i}] {zf.name}  ({mtime}, {size_kb:.1f} KB)")

    try:
        choice = input("\nChoose backup to restore (number): ").strip()
        idx = int(choice) - 1
        if idx < 0 or idx >= len(zip_files):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input. Please enter a number.")
        return

    selected = zip_files[idx]

    confirm = input(f"Restore from '{selected.name}'? This will overwrite current files. (y/n): ").strip().lower()
    if confirm != "y":
        print("Restore cancelled.")
        return

    with zipfile.ZipFile(selected, "r") as zf:
        zf.extractall(PROJECT_DIR)

    print(f"Restored from: {selected.name}")


def handle_command(command):
    cmd = command.strip().lower()
    if cmd == "py.backup":
        backup()
        return True
    elif cmd == "py.restore":
        restore()
        return True
    return False
