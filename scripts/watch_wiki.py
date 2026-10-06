#!/usr/bin/env python3
"""
watch_wiki.py — 파일 변경 감지 → 자동 위키 갱신 데몬
=====================================================
Raw/ 폴더 변경 → ingest + build_graph + build_home 자동 실행
Wiki/*.md 변경 → build_graph + build_home 자동 실행

의존: pip install watchdog

실행:
    python watch_wiki.py              # Raw/ + Wiki/ 감시 (기본)
    python watch_wiki.py --wiki-only  # Wiki/ 만 감시 (빠름)
    python watch_wiki.py --dry-run    # ingest 시 AI 호출 없음
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("❌ watchdog 미설치. 먼저 실행:")
    print("   pip install watchdog")
    print("   또는 setup_watch.bat 실행")
    sys.exit(1)

BASE    = Path(__file__).parent.parent
RAW_DIR = BASE / "Raw"
WIKI_DIR = BASE / "Wiki"

# 감시 제외 패턴
IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build",
               "release", ".claude", "GraphData"}
IGNORE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".exe", ".zip",
               ".ico", ".woff", ".woff2", ".ttf", ".mp3", ".mp4", ".db",
               ".html"}  # home.html / graph.html 변경은 무시


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def run(cmd: list[str], label: str) -> bool:
    """서브프로세스 실행, 성공 여부 반환"""
    print(f"  [{ts()}] ▶ {label}")
    r = subprocess.run(
        [sys.executable] + cmd,
        cwd=str(BASE),
        capture_output=False,
    )
    ok = r.returncode == 0
    status = "✅" if ok else "⚠️ 오류"
    print(f"  [{ts()}] {status} {label} (종료코드 {r.returncode})")
    return ok


class DebounceTimer:
    """변경 이벤트를 묶어 딜레이 후 한 번만 콜백 실행"""
    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self._timer = None
        self._callback = None

    def schedule(self, callback):
        import threading
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
        self._timer = threading.Timer(self.delay, callback)
        self._timer.start()


class RawHandler(FileSystemEventHandler):
    """Raw/ 변경 감지 → ingest → build_graph → build_home"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._debounce = DebounceTimer(delay=3.0)  # Raw 변경은 3초 대기
        self._changed_projects: set[str] = set()

    def _should_ignore(self, path: str) -> bool:
        p = Path(path)
        if p.suffix.lower() in IGNORE_EXTS:
            return True
        for part in p.parts:
            if part in IGNORE_DIRS:
                return True
        return False

    def _get_project(self, path: str) -> str | None:
        """파일 경로에서 Raw/ 하위 첫 번째 폴더명(프로젝트명) 추출"""
        try:
            rel = Path(path).relative_to(RAW_DIR)
            return rel.parts[0] if rel.parts else None
        except ValueError:
            return None

    def on_any_event(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return

        proj = self._get_project(event.src_path)
        if proj:
            self._changed_projects.add(proj)

        print(f"\n[{ts()}] 📝 Raw 변경 감지: {Path(event.src_path).name}")
        self._debounce.schedule(self._rebuild)

    def _rebuild(self):
        projects = list(self._changed_projects)
        self._changed_projects.clear()

        print(f"\n{'='*50}")
        print(f"[{ts()}] 🔄 자동 갱신 시작 (변경: {', '.join(projects) or '전체'})")
        print(f"{'='*50}")

        # ingest: 변경된 프로젝트만 (또는 여러 개면 전체)
        if len(projects) == 1:
            ingest_args = ["ingest.py", projects[0]]
        else:
            ingest_args = ["ingest.py"]

        if self.dry_run:
            ingest_args.append("--dry-run")

        run(ingest_args, "ingest.py")
        run(["build_graph.py"], "build_graph.py")
        run(["build_home.py"], "build_home.py")
        print(f"[{ts()}] ✅ 갱신 완료\n")


class WikiHandler(FileSystemEventHandler):
    """Wiki/*.md 변경 감지 → build_graph → build_home"""

    def __init__(self):
        self._debounce = DebounceTimer(delay=2.0)

    def _should_ignore(self, path: str) -> bool:
        p = Path(path)
        if p.suffix.lower() in IGNORE_EXTS:
            return True
        for part in p.parts:
            if part in IGNORE_DIRS:
                return True
        # home.html 등 자동 생성 파일 무시
        if p.name in {"home.html", "graph.html", "graph.json"}:
            return True
        return False

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if not event.src_path.endswith(".md"):
            return

        print(f"\n[{ts()}] 📝 Wiki 변경 감지: {Path(event.src_path).name}")
        self._debounce.schedule(self._rebuild)

    on_created = on_modified

    def _rebuild(self):
        print(f"\n{'='*50}")
        print(f"[{ts()}] 🔄 Wiki 갱신 시작")
        print(f"{'='*50}")
        run(["build_graph.py"], "build_graph.py")
        run(["build_home.py"], "build_home.py")
        print(f"[{ts()}] ✅ 갱신 완료\n")


def main():
    args = sys.argv[1:]
    wiki_only = "--wiki-only" in args
    dry_run   = "--dry-run"   in args

    print("=" * 50)
    print(" 🔭 LLM Wiki 자동 갱신 데몬")
    print("=" * 50)
    print(f"  기준 폴더: {BASE}")
    print(f"  감시 대상: {'Wiki/ 만' if wiki_only else 'Raw/ + Wiki/'}")
    if dry_run:
        print("  모드: dry-run (AI 호출 없음)")
    print("  중지: Ctrl+C")
    print()

    observer = Observer()

    if not wiki_only:
        if not RAW_DIR.exists():
            print(f"⚠️  Raw/ 폴더 없음 ({RAW_DIR}) — Raw 감시 건너뜀")
        else:
            raw_handler = RawHandler(dry_run=dry_run)
            observer.schedule(raw_handler, str(RAW_DIR), recursive=True)
            print(f"  👁 Raw/ 감시 중...")

    if WIKI_DIR.exists():
        wiki_handler = WikiHandler()
        observer.schedule(wiki_handler, str(WIKI_DIR), recursive=True)
        print(f"  👁 Wiki/ 감시 중...")
    else:
        print(f"⚠️  Wiki/ 폴더 없음 ({WIKI_DIR})")

    print()
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print(f"\n[{ts()}] 데몬 중지됨")
    observer.join()


if __name__ == "__main__":
    main()
