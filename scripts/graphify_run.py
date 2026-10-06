#!/usr/bin/env python3
"""
graphify_run.py — Graphify AST 코드 구조 추출기
================================================
pip install graphifyy 로 설치된 패키지를 사용하여
Raw/ 폴더의 코드 프로젝트를 토큰 없이 지식 그래프로 변환합니다.

사용법 (cmd에서 직접):
    python graphify_run.py                          # 전체 9개 프로젝트
    python graphify_run.py MBO_업무일지관리시스템    # 특정 프로젝트 1개
    python graphify_run.py --list                   # 프로젝트 목록 + 완료 여부
    python graphify_run.py --status                 # 설치 상태 확인

출력 위치:
    Wiki/GraphData/{프로젝트명}/
    ├── graph.json        ← 지식 그래프 (세션 간 유지)
    ├── GRAPH_REPORT.md   ← 허브 노드·커뮤니티 분석 리포트
    └── graph.html        ← 인터랙티브 브라우저 시각화
"""

import sys
import json
import time
import argparse
from pathlib import Path

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
VAULT      = Path(__file__).parent.parent          # 개발프로그램/
RAW_DIR    = VAULT / "Raw"
GRAPH_DATA = VAULT / "Wiki" / "GraphData"
GRAPH_DATA.mkdir(parents=True, exist_ok=True)

# graphify AST 대상 확장자 (SKILL.md 기준)
CODE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java",
                   ".c", ".cpp", ".rb", ".cs", ".kt", ".scala", ".php"}

# 제외 폴더 (node_modules, dist, build 등은 생성 파일이므로 제외)
SKIP_DIRS = {"node_modules", "dist", "build", ".git", "__pycache__",
             ".venv", "venv", "env", ".next", "coverage"}


# ── graphify 설치 확인 ────────────────────────────────────────────────────────
def check_graphify() -> bool:
    try:
        import graphify  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_graphify():
    if check_graphify():
        return
    print("\n❌  graphify 패키지가 없습니다.")
    print("    setup_graphify.bat 을 더블클릭하여 설치 후 재실행하세요.")
    print("    또는: pip install graphifyy")
    sys.exit(1)


# ── 출력 헬퍼 ─────────────────────────────────────────────────────────────────
def step(n, msg):
    print(f"\n  [{n}] {msg}", flush=True)

def ok(msg):
    print(f"      ✅ {msg}", flush=True)

def warn(msg):
    print(f"      ⚠️  {msg}", flush=True)

def err(msg):
    print(f"      ❌ {msg}", flush=True)


# ── 코드 파일 수집 (node_modules 등 제외) ────────────────────────────────────
def collect_code_files(project_path: Path) -> list:
    """
    프로젝트에서 AST 분석 가능한 코드 파일만 수집.
    node_modules, dist, build 폴더는 제외.
    """
    code_files = []
    for f in project_path.rglob("*"):
        if not f.is_file():
            continue
        # 제외 폴더 확인
        if any(skip in f.parts for skip in SKIP_DIRS):
            continue
        if f.suffix.lower() in CODE_EXTENSIONS:
            code_files.append(f)
    return code_files


# ── 문서 파일 수집 (AI 없이 메타데이터만) ─────────────────────────────────────
def collect_doc_nodes(project_path: Path) -> list:
    """
    .md / .txt 파일을 문서 노드로 변환 (AI 없이 파일명만 사용).
    """
    doc_extensions = {".md", ".txt", ".rst"}
    nodes = []
    for f in project_path.rglob("*"):
        if not f.is_file():
            continue
        if any(skip in f.parts for skip in SKIP_DIRS):
            continue
        if f.suffix.lower() not in doc_extensions:
            continue
        # Schema/CLAUDE.md 등 시스템 파일은 스킵
        if f.name == "CLAUDE.md":
            continue
        node_id = f"doc_{f.stem.replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')}"
        nodes.append({
            "id": node_id,
            "label": f.stem,
            "file_type": "document",
            "source_file": str(f.relative_to(VAULT)),
            "source_location": None,
            "source_url": None,
            "captured_at": None,
            "author": None,
            "contributor": None
        })
    return nodes


# ── HTML 전용 프로젝트 처리 (명언아카이브, 필사타자 등) ─────────────────────
def collect_html_nodes(project_path: Path) -> list:
    """
    HTML + JSON 파일에서 기본 구조 노드 추출.
    JavaScript 함수명을 간단 정규식으로 추출.
    """
    import re
    nodes = []
    edges = []

    for f in project_path.rglob("*.html"):
        if any(skip in f.parts for skip in SKIP_DIRS):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            # <script>에서 함수명 추출
            fn_names = re.findall(r"function\s+(\w+)\s*\(", content)
            # HTML 파일 자체 노드
            html_id = f"html_{f.stem.replace(' ', '_')}"
            nodes.append({
                "id": html_id,
                "label": f.stem,
                "file_type": "code",
                "source_file": str(f.relative_to(VAULT)),
                "source_location": None,
                "source_url": None,
                "captured_at": None,
                "author": None,
                "contributor": None
            })
            # 함수 노드 및 엣지
            for fn in set(fn_names):
                if len(fn) < 3 or fn in {"main", "init", "load"}:
                    continue
                fn_id = f"fn_{fn}"
                nodes.append({
                    "id": fn_id,
                    "label": fn,
                    "file_type": "code",
                    "source_file": str(f.relative_to(VAULT)),
                    "source_location": None,
                    "source_url": None,
                    "captured_at": None,
                    "author": None,
                    "contributor": None
                })
                edges.append({
                    "source": html_id,
                    "target": fn_id,
                    "relation": "defines",
                    "confidence": "EXTRACTED",
                    "source_file": str(f.relative_to(VAULT)),
                    "source_location": None,
                    "weight": 1.0
                })
        except Exception:
            pass

    return nodes, edges


# ── 단일 프로젝트 처리 ────────────────────────────────────────────────────────
def run_project(project_path: Path) -> bool:
    """단일 프로젝트 Graphify 파이프라인 실행. True = 성공."""
    pname   = project_path.name
    out_dir = GRAPH_DATA / pname
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*62}")
    print(f"  📁  {pname}")
    print(f"{'='*62}")

    # ── imports ──────────────────────────────────────────────────────────
    try:
        from graphify.extract import extract
        from graphify.build   import build_from_json
        from graphify.cluster import cluster, score_all
        from graphify.analyze import god_nodes, surprising_connections, suggest_questions
        from graphify.report  import generate
        from graphify.export  import to_json, to_html
    except ImportError as e:
        err(f"graphify 모듈 로드 실패: {e}")
        err("setup_graphify.bat 를 다시 실행하세요.")
        return False

    # ── 1단계: 코드 파일 수집 ─────────────────────────────────────────────
    step(1, "코드 파일 수집 중 (node_modules 등 제외)...")
    code_files = collect_code_files(project_path)

    by_ext: dict = {}
    for f in code_files:
        ext = f.suffix.lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1
    ext_summary = "  ".join(f"{ext}:{cnt}" for ext, cnt in sorted(by_ext.items()))
    print(f"      코드 파일: {len(code_files)}개  ({ext_summary or '없음'})")

    # 대용량 프로젝트 경고 (200개 초과)
    if len(code_files) > 200:
        warn(f"파일 수 {len(code_files)}개 — 대용량 프로젝트입니다 (처리 시간이 길 수 있음)")
        warn("상위 200개 파일만 분석합니다 (핵심 소스 우선)")
        # src/ 폴더 우선, 그 다음 나머지 순서로 200개 선택
        src_files = [f for f in code_files if "src" in f.parts or "core" in f.parts]
        other_files = [f for f in code_files if f not in src_files]
        code_files = (src_files + other_files)[:200]
        print(f"      → 선택된 파일: {len(code_files)}개 (src/core 우선)")

    # ── 2단계: AST 추출 (코드 파일) ──────────────────────────────────────
    step(2, "AST 추출 중 (토큰 없음)...")
    ast_nodes, ast_edges = [], []

    if code_files:
        try:
            result = extract(code_files)
            ast_nodes = result.get("nodes", [])
            ast_edges = result.get("edges", [])
            ok(f"AST 완료 — 노드 {len(ast_nodes)}개, 엣지 {len(ast_edges)}개")
        except Exception as e:
            warn(f"AST 추출 오류: {e}")
            warn("코드 파일 파싱 건너뜁니다.")
    else:
        ok("코드 파일 없음 — HTML 기반 프로젝트로 처리합니다.")

    # ── 3단계: HTML 보조 추출 (코드 없는 프로젝트용) ─────────────────────
    html_nodes, html_edges = [], []
    if not code_files:
        step(3, "HTML 파일에서 함수 구조 추출 중...")
        html_nodes, html_edges = collect_html_nodes(project_path)
        if html_nodes:
            ok(f"HTML 노드: {len(html_nodes)}개, 엣지: {len(html_edges)}개")
        else:
            ok("HTML 구조 없음.")
    else:
        step(3, "HTML 추출 건너뜀 (코드 파일 존재)")

    # ── 4단계: 문서 메타데이터 추출 (AI 없이) ────────────────────────────
    step(4, "문서 파일 메타데이터 추출 중 (AI 없음)...")
    doc_nodes = collect_doc_nodes(project_path)
    ok(f"문서 노드: {len(doc_nodes)}개")

    # ── 5단계: 전체 병합 ──────────────────────────────────────────────────
    step(5, "전체 노드/엣지 병합 중...")
    seen_ids = set()
    all_nodes = []
    for node in ast_nodes + html_nodes + doc_nodes:
        nid = node.get("id", "")
        if nid and nid not in seen_ids:
            all_nodes.append(node)
            seen_ids.add(nid)
    all_edges = ast_edges + html_edges

    ok(f"최종 — 노드 {len(all_nodes)}개, 엣지 {len(all_edges)}개")

    if len(all_nodes) == 0:
        warn("노드가 없습니다. 이 프로젝트는 건너뜁니다.")
        return False

    merged = {
        "nodes": all_nodes,
        "edges": all_edges,
        "input_tokens": 0,
        "output_tokens": 0
    }

    # ── 6단계: 그래프 빌드 + 클러스터링 ─────────────────────────────────
    step(6, "그래프 빌드 및 커뮤니티 클러스터링 중...")
    try:
        G = build_from_json(merged)

        if G.number_of_nodes() == 0:
            warn("그래프가 비어있습니다.")
            return False

        communities = cluster(G)
        cohesion    = score_all(G, communities)
        gods        = god_nodes(G)
        surprises   = surprising_connections(G, communities)
        labels      = {cid: f"그룹{cid}" for cid in communities}
        questions   = suggest_questions(G, communities, labels)

        ok(f"클러스터링 완료 — "
           f"{G.number_of_nodes()}개 노드, "
           f"{G.number_of_edges()}개 엣지, "
           f"{len(communities)}개 커뮤니티")
    except Exception as e:
        err(f"그래프 빌드 실패: {e}")
        import traceback; traceback.print_exc()
        return False

    # ── 7단계: 출력 파일 생성 ─────────────────────────────────────────────
    step(7, "출력 파일 생성 중...")

    # detection 더미 (report.generate 필요 인수)
    detection = {
        "total_files": len(code_files) + len(doc_nodes) + len(html_nodes),
        "total_words": 0,
        "files": {
            "code": [str(f) for f in code_files],
            "docs": [],
            "images": []
        }
    }
    tokens = {"input": 0, "output": 0}

    saved = []
    try:
        report = generate(
            G, communities, cohesion, labels,
            gods, surprises, detection, tokens,
            str(project_path),
            suggested_questions=questions
        )
        (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
        saved.append("GRAPH_REPORT.md")
    except Exception as e:
        warn(f"GRAPH_REPORT 생성 오류: {e}")

    try:
        to_json(G, communities, str(out_dir / "graph.json"))
        saved.append("graph.json")
    except Exception as e:
        warn(f"graph.json 생성 오류: {e}")

    try:
        if G.number_of_nodes() <= 5000:
            to_html(G, communities, str(out_dir / "graph.html"),
                    community_labels=labels)
            saved.append("graph.html")
    except Exception as e:
        warn(f"graph.html 생성 오류: {e}")

    if saved:
        ok(f"저장 완료: {', '.join(saved)} → Wiki/GraphData/{pname}/")
    else:
        warn("저장된 파일이 없습니다.")
        return False

    # ── 8단계: 핵심 결과 요약 ────────────────────────────────────────────
    print(f"\n  📊 {pname} 분석 결과")

    try:
        if gods:
            print(f"  🏆 허브 노드 (연결 집중, 상위 5개):")
            for g in gods[:5]:
                # god_nodes()는 node ID(str) 또는 dict를 반환할 수 있음
                if isinstance(g, dict):
                    node_id = (g.get("id") or g.get("node") or
                               g.get("name") or next(iter(g.values()), None))
                else:
                    node_id = g
                try:
                    if node_id and node_id in G.nodes:
                        name = G.nodes[node_id].get("label", str(node_id))
                        deg  = G.degree(node_id)
                        src  = G.nodes[node_id].get("source_file", "")
                        print(f"     · {name}  (연결 {deg}개)  ← {Path(src).name if src else ''}")
                except Exception:
                    pass
    except Exception:
        pass

    try:
        if questions:
            print(f"  💡 탐색 추천 질문:")
            for q in questions[:3]:
                print(f"     · {q}")
    except Exception:
        pass

    return True


# ── 전체 프로젝트 실행 ────────────────────────────────────────────────────────
def run_all():
    projects = get_projects()
    if not projects:
        print("❌ Raw/ 폴더에 프로젝트가 없습니다.")
        return

    print(f"\n총 {len(projects)}개 프로젝트를 순서대로 분석합니다.")
    print("(각 프로젝트는 토큰 없이 AST 기반으로 처리됩니다)\n")

    success, skipped, failed = 0, 0, []
    t_total = time.time()

    for proj in projects:
        t0 = time.time()
        try:
            result = run_project(proj)
            elapsed = time.time() - t0
            if result:
                print(f"\n  ✅ {proj.name} 완료 ({elapsed:.0f}초)")
                success += 1
            else:
                print(f"\n  ⬜ {proj.name} 건너뜀")
                skipped += 1
        except Exception as e:
            err(f"{proj.name} 처리 중 예외: {e}")
            failed.append(proj.name)

    total_elapsed = time.time() - t_total
    print(f"\n{'='*62}")
    print(f"  전체 완료: {success}개 성공 / {skipped}개 건너뜀 / {len(failed)}개 오류")
    print(f"  총 소요 시간: {total_elapsed:.0f}초 | 토큰 사용: 0개")
    if failed:
        print(f"  오류 프로젝트: {', '.join(failed)}")
    print(f"  결과 폴더: Wiki/GraphData/")
    print(f"{'='*62}")


# ── 유틸리티 ──────────────────────────────────────────────────────────────────
def get_projects() -> list:
    if not RAW_DIR.exists():
        return []
    return [d for d in sorted(RAW_DIR.iterdir())
            if d.is_dir() and not d.name.startswith(".")]


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Graphify — 코드 AST 지식 그래프 생성 (토큰 없음)"
    )
    parser.add_argument(
        "project", nargs="?",
        help="프로젝트 폴더명 (Raw/ 하위). 생략 시 전체 실행."
    )
    parser.add_argument("--list",   action="store_true", help="프로젝트 목록 + 완료 여부")
    parser.add_argument("--status", action="store_true", help="설치 상태 확인")
    args = parser.parse_args()

    # ── 상태 확인 ──────────────────────────────────────────────────────────
    if args.status:
        if check_graphify():
            import graphify
            ver = getattr(graphify, "__version__", "알 수 없음")
            print(f"✅ graphify v{ver} 설치됨")
        else:
            print("❌ graphify 미설치")
            print("   setup_graphify.bat 을 실행하세요.")
        print(f"   Raw 폴더:    {RAW_DIR}")
        print(f"   출력 폴더:   {GRAPH_DATA}")
        return

    # ── 목록 ───────────────────────────────────────────────────────────────
    if args.list:
        projects = get_projects()
        print(f"\n분석 가능한 프로젝트 ({len(projects)}개):")
        for p in projects:
            code_cnt = len(collect_code_files(p))
            done_mark = "✅" if (GRAPH_DATA / p.name / "graph.json").exists() else "⬜"
            print(f"  {done_mark} {p.name:40s} 코드: {code_cnt}개")
        return

    # ── graphify 설치 확인 ─────────────────────────────────────────────────
    ensure_graphify()

    # ── 단일 프로젝트 ──────────────────────────────────────────────────────
    if args.project:
        proj_path = RAW_DIR / args.project
        if not proj_path.exists():
            print(f"\n❌ 폴더 없음: {proj_path}")
            print("   --list 로 프로젝트 목록을 확인하세요.")
            sys.exit(1)
        t0 = time.time()
        ok_flag = run_project(proj_path)
        elapsed = time.time() - t0
        if ok_flag:
            print(f"\n✅ 완료! ({elapsed:.0f}초)")
            graph_html = GRAPH_DATA / args.project / "graph.html"
            if graph_html.exists():
                print(f"   브라우저 시각화: Wiki/GraphData/{args.project}/graph.html")
            print(f"   분석 리포트:     Wiki/GraphData/{args.project}/GRAPH_REPORT.md")
        else:
            print(f"\n⬜ 분석 결과 없음 (코드 파일 부족 또는 오류)")
    else:
        run_all()


if __name__ == "__main__":
    main()
