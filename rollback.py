#!/usr/bin/env python3
"""Sebastian — automatyczny skrypt przywracania (rollback) do stanu sprzed wersji 1.3."""
import os
from pathlib import Path
import shutil

def main():
    root = Path.cwd().resolve()
    if not (root / 'sebastian.py').is_file() and not (root / 'backups').is_dir():
        raise RuntimeError("Uruchom ten skrypt z głównego folderu sebastian-start.")

    backups_dir = root / 'backups'
    if not backups_dir.is_dir():
        raise RuntimeError("Brak folderu backups. Nie ma z czego przywrócić kopii.")

    # Znajdź najnowszy folder kopii zapasowej w folderze backups
    backup_folders = sorted([f for f in backups_dir.iterdir() if f.is_dir()], key=lambda x: x.stat().mtime, reverse=True)
    
    if not backup_folders:
        raise RuntimeError("Nie znaleziono żadnych folderów z kopiami zapasowymi w 'backups'.")

    target_backup = backup_folders[0]
    print(f"📦 Znaleziono najnowszą kopię zapasową: {target_backup.name}")

    data_dir = root / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Przywracanie plików (sebastian.py, templates/ itp.)
    files_backup_dir = target_backup / 'files'
    if files_backup_dir.is_dir():
        for src_path in files_backup_dir.glob('**/*'):
            if src_path.is_file():
                rel_path = src_path.relative_to(files_backup_dir)
                dest_path = root / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
                print(f"  ↳ Przywrócono plik: {rel_path}")

    # 2. Przywracanie bazy danych
    db_backup = target_backup / 'sebastian.sqlite3'
    if db_backup.is_file():
        db_dest = data_dir / 'sebastian.sqlite3'
        shutil.copy2(db_backup, db_dest)
        print("  ↳ Przywrócono bazę danych (sebastian.sqlite3)")

    # 3. Przywracanie config.json
    config_backup = target_backup / 'config.json'
    if config_backup.is_file():
        config_dest = data_dir / 'config.json'
        shutil.copy2(config_backup, config_dest)
        print("  ↳ Przywrócono plik konfiguracyjny (config.json)")

    print("\n✅ Pomyślnie przywrócono system z kopii zapasowej!")
    print("🚀 Możesz teraz uruchomić panel poleceniem: python sebastian.py serve")

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f"❌ BŁĄD: {exc}")