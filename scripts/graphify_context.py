#!/usr/bin/env python3
"""
graphify_context.py — Graphify 결과를 Claude 에이전트용 컨텍스트로 변환

사용법:
    python graphify_context.py                    # 전체 GraphData 요약
    python graphify_context.py 프로젝트명          # 특정 프로젝트 그래프 요약
    python graphify_context.py --query "SQLite"   # 특정 개념 검색

이 스크립트 출력을 Claude 프롬프트에 붙여넣으면
AI 토큰 없이 코드 구조 컨텍스트를 에이전트에게 전달 가능.
"""

import json
import sys
import argparse
from pathlib import Path

VAULT = Path(__file__).parent.parent
GRAPH_DATA = VAULT / "Wiki" / "GraphData"


def load_graph(project: str = "_all") -> dict | None:
    """graphify가 생성한 graph.json 로드"""
    graph_file = GRAPH_DATA / project / "graph.json"
    if not graph_file.exists():
        print(f"[오류] graph.json 없음: {graph_file}")
        print(f"       run_graphify.bat {project} 를 먼저 실행하세요.")
        return None
    return json.loads(graph_file.read_text(encoding="utf-8"))


def load_report(project: str = "_all") -> str:
    """GRAPH_REPORT.md 로드"""
    report_file = GRAPH_DATA / project / "GRAPH_REPORT.md"
    if report_file.exists():
        return report_file.read_text(encoding="utf-8")
    return ""


def summarize_graph(data: dict, max_nodes: int = 30) -> str:
    """graph.json → Claude 프롬프트용 텍스트 요약"""
    try:
        # networkx 사용 가능 시
        import networkx as nx
        from networkx.readwrite import json_graph
        G = json_graph.node_link_graph(data, edges="links")
    except ImportError:
        # 없으면 수동 파싱
        G = None

    lines = ["=== GRAPHIFY 코드 구조 요약 (AST 기반, 토큰 0) ===", ""]

    if G:
        # 허브 노드 (연결 많은 순)
        top_nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:max_nodes]
        lines.append(f"## 핵심 노드 (총 {G.number_of_nodes()}개 중 상위 {len(top_nodes)}개)")
        for nid in top_nodes:
            d = G.nodes[nid]
            degree = G.degree(nid)
            label = d.get("label", nid)
            src = d.get("source_file", "")
            lines.append(f"  - {label} [연결:{degree}] ← {src}")

        lines.append("")
        lines.append(f"## 엣지 샘플 (총 {G.number_of_edges()}개 중 30개)")
        for i, (u, v, d) in enumerate(G.edges(data=True)):
            if i >= 30:
                break
            rel = d.get("relation", "→")
            conf = d.get("confidence", "")
            lines.append(f"  {G.nodes[u].get('label', u)} --{rel} [{conf}]--> {G.nodes[v].get('label', v)}")
    else:
        # 수동 파싱
        nodes = data.get("nodes", data.get("links", []))
        if isinstance(nodes, list):
            lines.append(f"## 노드 ({len(nodes)}개)")
            for n in nodes[:max_nodes]:
                if isinstance(n, dict):
                    lines.append(f"  - {n.get('label', n.get('id', '?'))} ← {n.get('source_file', '')}")

    return "\n".join(lines)


def query_graph(data: dict, keyword: str) -> str:
    """특정 키워드와 관련된 노드/엣지 검색"""
    lines = [f"=== GRAPHIFY 쿼리: '{keyword}' ===", ""]

    try:
        import networkx as nx
        from networkx.readwrite import json_graph
        G = json_graph.node_link_graph(data, edges="links")

        kw = keyword.lower()
        matched = [n for n in G.nodes()
                   if kw in G.nodes[n].get("label", "").lower()
                   or kw in G.nodes[n].get("source_file", "").lower()]

        lines.append(f"## 매칭 노드 ({len(matched)}개)")
        for nid in matched:
            d = G.nodes[nid]
            lines.append(f"  NODE: {d.get('label', nid)}")
            lines.append(f"    파일: {d.get('source_file', '')}")
            # 이웃 노드
            neighbors = list(G.neighbors(nid))
            if neighbors:
                lines.append(f"    연결: {', '.join(G.nodes[nb].get('label', nb) for nb in neighbors[:5])}")
    except ImportError:
        lines.append("[networkx 미설치] pip install networkx")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Graphify 결과 → Claude 컨텍스트 변환")
    parser.add_argument("project", nargs="?", default="_all", help="프로젝트명 (기본: _all)")
    parser.add_argument("--query", "-q", help="특정 개념 검색")
    parser.add_argument("--report", "-r", action="store_true", help="GRAPH_REPORT.md 출력")
    parser.add_argument("--list", "-l", action="store_true", help="사용 가능한 그래프 목록")
    args = parser.parse_args()

    # 목록 출력
    if args.list:
        print("사용 가능한 Graphify 그래프:")
        if GRAPH_DATA.exists():
            for d in sorted(GRAPH_DATA.iterdir()):
                if d.is_dir() and (d / "graph.json").exists():
                    print(f"  - {d.name}")
        else:
            print("  (없음) run_graphify.bat 를 먼저 실행하세요.")
        return

    data = load_graph(args.project)
    if data is None:
        return

    # 쿼리 모드
    if args.query:
        print(query_graph(data, args.query))
        return

    # 리포트 모드
    if args.report:
        report = load_report(args.project)
        if report:
            # 핵심 섹션만 출력 (전체는 너무 길 수 있음)
            lines = report.split("\n")
            print("\n".join(lines[:80]))
        else:
            print("GRAPH_REPORT.md 없음")
        return

    # 기본: 그래프 요약
    print(summarize_graph(data))


if __name__ == "__main__":
    main()
