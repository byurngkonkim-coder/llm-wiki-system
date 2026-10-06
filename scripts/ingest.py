#!/usr/bin/env python3
"""
ingest.py — Raw 프로젝트 → Wiki/Summaries 자동 생성
=====================================================
P1-3: Ollama 연동 — from ai_router import ask_ai

실행:
    python ingest.py               # 전체 처리
    python ingest.py MBO_업무일지  # 특정 프로젝트만
    python ingest.py --dry-run     # AI 호출 없이 파일 통계만
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))   # ai_router 임포트 경로

from ai_router import ask_ai, is_ollama_running   # P1-3

RAW_DIR        = BASE / "Raw"
WIKI_SUMMARIES = BASE / "Wiki" / "Summaries"

# 확장자 → 기술 스택 매핑
TECH_MAP = {
    ".py":   "Python",
    ".ts":   "TypeScript",
    ".tsx":  "TypeScript",
    ".js":   "JavaScript",
    ".jsx":  "JavaScript",
    ".sql":  "SQL",
    ".html": "HTML",
    ".css":  "CSS",
}

# 무시할 디렉터리 / 확장자
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", "release", ".claude"}
SKIP_EXT  = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".exe", ".zip",
             ".ico", ".woff", ".woff2", ".ttf", ".mp3", ".mp4", ".db"}

SYSTEM_PROMPT = (
    "당신은 소프트웨어 개발 문서 전문가입니다. "
    "주어진 프로젝트 정보를 바탕으로 Obsidian 마크다운 형식으로 "
    "간결하고 실용적인 위키 문서를 한국어로 작성하세요."
)


# ── 프로젝트 스캔 ─────────────────────────────────────────────────────────────

def scan_project(proj_dir: Path) -> dict:
    """프로젝트 디렉터리 → 파일 통계 + 코드 샘플"""
    files_by_tech: dict[str, int] = {}
    all_files: list[str] = []
    code_samples: list[str] = []

    for root, dirs, files in os.walk(proj_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            p = Path(root) / fn
            ext = p.suffix.lower()
            if ext in SKIP_EXT:
                continue
            tech = TECH_MAP.get(ext, "기타")
            files_by_tech[tech] = files_by_tech.get(tech, 0) + 1
            rel = p.relative_to(proj_dir)
            all_files.append(str(rel).replace("\\", "/"))

            # 코드 샘플: .py / .ts / .js 파일 최대 3개, 각 30줄
            if ext in (".py", ".ts", ".tsx", ".js", ".jsx") and len(code_samples) < 3:
                try:
                    lines = p.read_text("utf-8", errors="ignore").splitlines()[:30]
                    code_samples.append(f"### {rel}\n```\n" + "\n".join(lines) + "\n```")
                except Exception:
                    pass

    main_tech = sorted(
        [(t, c) for t, c in files_by_tech.items() if t != "기타"],
        key=lambda x: -x[1],
    )

    return {
        "name":        proj_dir.name,
        "dir":         proj_dir,
        "files_by_tech": files_by_tech,
        "main_tech":   main_tech,
        "all_files":   all_files,
        "total_files": len(all_files),
        "code_samples": "\n\n".join(code_samples),
    }


# ── AI 요약 생성 ──────────────────────────────────────────────────────────────

def build_prompt(info: dict) -> str:
    tech_str = ", ".join(f"{t}({c}개)" for t, c in info["main_tech"][:5]) or "미확인"
    files_str = "\n".join(f"  - {f}" for f in info["all_files"][:20])
    if len(info["all_files"]) > 20:
        files_str += f"\n  - ... 외 {len(info['all_files']) - 20}개"

    return f"""프로젝트: '{info['name']}'

기술 스택: {tech_str}
총 파일 수: {info['total_files']}개

주요 파일 목록:
{files_str}

코드 샘플:
{info['code_samples'][:2000]}

위 정보를 바탕으로 아래 마크다운 섹션만 작성하세요 (제목·frontmatter 제외):

## 프로젝트 개요
(목적과 핵심 기능 3줄 이내, - 불릿 형식)

## 주요 소스 파일
(중요 파일 5개 이내, 각 역할 한 줄)

## 관련 개념
(관련 기술 개념 3개, [[위키링크]] 형식)

## 관련 엔티티
(주요 라이브러리/프레임워크 3개, [[위키링크]] 형식)

반드시 한국어로 작성하세요."""


def ai_summarize(info: dict, dry_run: bool = False) -> str:
    """ask_ai 를 사용해 프로젝트 요약 생성 (P1-3)"""
    if dry_run:
        tech_str = ", ".join(t for t, _ in info["main_tech"][:5]) or "미확인"
        files_md = "\n".join(f"  - `{f}`" for f in info["all_files"][:10])
        return f"## 프로젝트 개요\n- 기술 스택: {tech_str}\n- 소스 파일: {info['total_files']}개\n\n## 주요 소스 파일\n{files_md}"

    prompt = build_prompt(info)
    return ask_ai(prompt, system=SYSTEM_PROMPT, verbose=True)


# ── Wiki 마크다운 생성 ────────────────────────────────────────────────────────

def make_summary_md(info: dict, ai_content: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    tags = [t for t, _ in info["main_tech"][:5]]
    tags_str = "[" + ", ".join(tags) + "]" if tags else "[]"

    # AI 응답에서 frontmatter·H1 제거 (중복 방지)
    body = re.sub(r"^---[\s\S]*?---\s*", "", ai_content).strip()
    body = re.sub(r"^#\s+.+\n", "", body).strip()

    return (
        f"---\n"
        f"source: Raw/{info['name']}\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"tags: {tags_str}\n"
        f"---\n\n"
        f"# {info['name']}\n\n"
        f"{body}\n"
    )


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    # 인자 파싱
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    target = next((a for a in args if not a.startswith("--")), None)

    if dry_run:
        print("🔍 Dry-run 모드 — AI 호출 없음")

    if not RAW_DIR.exists():
        print(f"[오류] Raw 디렉터리 없음: {RAW_DIR}")
        sys.exit(1)

    WIKI_SUMMARIES.mkdir(parents=True, exist_ok=True)

    # Ollama 상태 확인 (P1-3)
    if not dry_run:
        ollama_ok = is_ollama_running()
        print(f"{'✅ Ollama 실행 중' if ollama_ok else '⚠️  Ollama 미실행 — Claude API 폴백'}\n")

    # 처리할 프로젝트 목록
    projects = sorted(
        d for d in RAW_DIR.iterdir()
        if d.is_dir() and d.name not in SKIP_DIRS
        and (target is None or target.lower() in d.name.lower())
    )

    if not projects:
        msg = f"'{target}'" if target else RAW_DIR
        print(f"[경고] 처리할 프로젝트 없음: {msg}")
        return

    print(f"📦 {len(projects)}개 프로젝트 인제스트 시작\n")
    updated = []

    for proj in projects:
        print(f"  [{proj.name}]")
        info = scan_project(proj)

        tech_str = ", ".join(f"{t} {c}개" for t, c in info["main_tech"][:4]) or "미확인"
        print(f"    스택: {tech_str} | 총 파일: {info['total_files']}개")

        try:
            ai_content = ai_summarize(info, dry_run=dry_run)
        except Exception as e:
            print(f"    ⚠️  AI 오류: {e} — 기본 템플릿 사용")
            ai_content = ""

        md = make_summary_md(info, ai_content or "")
        out = WIKI_SUMMARIES / f"{proj.name}.md"
        out.write_text(md, encoding="utf-8")
        print(f"    ✅ Wiki/Summaries/{proj.name}.md 저장\n")
        updated.append(proj.name)

    print(f"✅ 인제스트 완료 — {len(updated)}개 처리")
    print("   다음: python build_home.py  또는  wiki_refresh.bat 실행")


if __name__ == "__main__":
    main()
