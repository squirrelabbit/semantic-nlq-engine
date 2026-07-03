import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class Entry:
    pattern: str
    table: str
    columns: List[str]
    delimiter: str
    header: bool
    encoding: str


def load_manifest(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("stable_seconds", 2)
    payload.setdefault("on_success", "archive")
    payload.setdefault("state_file", "data/.upload_state.json")
    payload.setdefault("archive_dir", "data/processed")
    return payload


def parse_entries(raw_entries: Iterable[Dict[str, Any]]) -> List[Entry]:
    entries = []
    for raw in raw_entries:
        entries.append(
            Entry(
                pattern=str(raw["pattern"]),
                table=str(raw["table"]),
                columns=[str(col) for col in raw["columns"]],
                delimiter=str(raw.get("delimiter", "|")),
                header=bool(raw.get("header", True)),
                encoding=str(raw.get("encoding", "utf-8-sig")),
            )
        )
    return entries


def load_state(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {str(k): float(v) for k, v in payload.items()}


def save_state(path: Path, state: Dict[str, float]) -> None:
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def is_file_stable(path: Path, stable_seconds: float) -> bool:
    if not path.exists():
        return False
    first = (path.stat().st_size, path.stat().st_mtime)
    time.sleep(stable_seconds)
    second = (path.stat().st_size, path.stat().st_mtime)
    return first == second


def find_entry(entries: List[Entry], filename: str) -> Optional[Entry]:
    for entry in entries:
        if fnmatch.fnmatch(filename, entry.pattern):
            return entry
    return None


def build_command(entry: Entry, file_path: Path) -> List[str]:
    cmd = [
        sys.executable,
        "scripts/load_csv.py",
        "--table",
        entry.table,
        "--csv",
        str(file_path),
        "--columns",
        ",".join(entry.columns),
        "--delimiter",
        entry.delimiter,
        "--encoding",
        entry.encoding,
    ]
    if entry.header:
        cmd.append("--header")
    return cmd


def process_file(
    entry: Entry,
    file_path: Path,
    on_success: str,
    archive_dir: Path,
    state: Dict[str, float],
    state_path: Path,
    stable_seconds: float,
) -> None:
    if not is_file_stable(file_path, stable_seconds):
        return
    cmd = build_command(entry, file_path)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        combined = f"{result.stdout}\n{result.stderr}".lower()
        if "duplicate key value violates unique constraint" in combined:
            print(f"[WARN] duplicate rows detected; archiving: {file_path}")
        else:
            print(f"[ERROR] load_csv failed: {file_path}", file=sys.stderr)
            if result.stderr:
                print(result.stderr.strip(), file=sys.stderr)
            return
    if on_success == "archive":
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(archive_dir / file_path.name))
    else:
        state[str(file_path)] = file_path.stat().st_mtime
        save_state(state_path, state)


def scan_once(
    watch_dir: Path,
    entries: List[Entry],
    on_success: str,
    archive_dir: Path,
    state: Dict[str, float],
    state_path: Path,
    stable_seconds: float,
) -> None:
    for path in sorted(watch_dir.iterdir()):
        if path.is_dir() or path.name.startswith("."):
            continue
        entry = find_entry(entries, path.name)
        if not entry:
            continue
        if on_success != "archive":
            mtime = path.stat().st_mtime
            if state.get(str(path)) == mtime:
                continue
        process_file(entry, path, on_success, archive_dir, state, state_path, stable_seconds)


def watch_loop(
    watch_dir: Path,
    entries: List[Entry],
    on_success: str,
    archive_dir: Path,
    state: Dict[str, float],
    state_path: Path,
    stable_seconds: float,
    poll_interval: float,
) -> None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        print("[WARN] watchdog not installed; falling back to polling.")
        while True:
            scan_once(
                watch_dir,
                entries,
                on_success,
                archive_dir,
                state,
                state_path,
                stable_seconds,
            )
            time.sleep(poll_interval)
        return

    class Handler(FileSystemEventHandler):
        def on_created(self, event) -> None:
            if event.is_directory:
                return
            path = Path(event.src_path)
            entry = find_entry(entries, path.name)
            if not entry:
                return
            process_file(entry, path, on_success, archive_dir, state, state_path, stable_seconds)

        def on_moved(self, event) -> None:
            if event.is_directory:
                return
            path = Path(event.dest_path)
            entry = find_entry(entries, path.name)
            if not entry:
                return
            process_file(entry, path, on_success, archive_dir, state, state_path, stable_seconds)

    observer = Observer()
    observer.schedule(Handler(), str(watch_dir), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch data/ for new files and load via manifest.")
    parser.add_argument(
        "--manifest",
        default="data/upload_manifest.json",
        help="Path to upload manifest JSON.",
    )
    parser.add_argument("--once", action="store_true", help="Process existing files and exit.")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = load_manifest(manifest_path)
    watch_dir = Path(manifest["watch_dir"])
    entries = parse_entries(manifest.get("entries", []))
    on_success = str(manifest.get("on_success", "archive"))
    archive_dir = Path(manifest.get("archive_dir", "data/processed"))
    state_path = Path(manifest.get("state_file", "data/.upload_state.json"))
    stable_seconds = float(manifest.get("stable_seconds", 2))
    state = load_state(state_path)

    if args.once:
        scan_once(
            watch_dir,
            entries,
            on_success,
            archive_dir,
            state,
            state_path,
            stable_seconds,
        )
        return 0

    watch_loop(
        watch_dir,
        entries,
        on_success,
        archive_dir,
        state,
        state_path,
        stable_seconds,
        args.poll_interval,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
