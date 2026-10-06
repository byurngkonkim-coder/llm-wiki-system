#!/usr/bin/env python3
"""
build_graph.py — Wiki 지식 그래프 재생성
==========================================
Wiki/*.md 파일을 분석하여 프로젝트 간 연결 관계를 추출하고
Wiki/GraphData/graph.json 과 graph.html 을 재생성합니다.

엣지 생성 규칙:
  1. 공유 토픽   — 같은 Topics/*.md 에 언급된 프로젝트끼리
  2. 위키 링크   — [[링크]]로 서로 참조하는 문서끼리
  3. 배포 관계   — 'release_' 접두어를 가진 Summary가 원본 프로젝트와 연결

실행:
    python build_graph.py
    python build_graph.py --verbose
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
WIKI = BASE / "Wiki"
OUT_JSON = WIKI / "GraphData" / "graph.json"
OUT_HTML = WIKI / "GraphData" / "graph.html"

SKIP_FILES = {"index.md", "log.md", "hot.md", "GRAPH_REPORT.md"}
VERBOSE = "--verbose" in sys.argv


def log(msg):
    if VERBOSE:
        print(f"  {msg}")


# ── 1. 노드 수집 ──────────────────────────────────────────────────────────────

def collect_nodes() -> dict[str, dict]:
    """Wiki/Summaries, Concepts, Entities, Topics 에서 노드 수집"""
    nodes = {}
    for subdir, kind in [("Summaries", "project"), ("Concepts", "concept"),
                         ("Entities", "entity"), ("Topics", "topic")]:
        d = WIKI / subdir
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            nid = p.stem
            nodes[nid] = {
                "id":    nid,
                "kind":  kind,
                "path":  str(p.relative_to(WIKI)).replace("\\", "/"),
            }
            log(f"노드: [{kind}] {nid}")
    return nodes


# ── 2. [[wikilink]] 추출 ─────────────────────────────────────────────────────

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def extract_wikilinks(md_text: str) -> list[str]:
    """[[링크]] 에서 파일명(stem) 추출"""
    links = []
    for raw in WIKILINK_RE.findall(md_text):
        # 경로에서 파일명만 추출 (Summaries/MBO... → MBO...)
        stem = Path(raw.strip()).stem
        links.append(stem)
    return links


def collect_wikilink_edges(nodes: dict) -> list[dict]:
    """모든 Wiki .md 파일에서 [[링크]] 엣지 수집"""
    edges = []
    seen = set()

    for p in sorted(WIKI.rglob("*.md")):
        if p.name in SKIP_FILES:
            continue
        src_stem = p.stem
        if src_stem not in nodes:
            continue

        text = p.read_text("utf-8", errors="ignore")
        for tgt_stem in extract_wikilinks(text):
            if tgt_stem not in nodes:
                continue
            if src_stem == tgt_stem:
                continue
            key = tuple(sorted([src_stem, tgt_stem])) + ("참조",)
            if key in seen:
                continue
            seen.add(key)
            edges.append({
                "source":   src_stem,
                "target":   tgt_stem,
                "relation": "참조",
                "shared":   [],
            })
            log(f"링크 엣지: {src_stem} → {tgt_stem}")

    return edges


# ── 3. 공유 토픽 엣지 ─────────────────────────────────────────────────────────

def collect_topic_edges(nodes: dict) -> list[dict]:
    """Topics/*.md 에 언급된 Summary가 같은 토픽 → '공유개념' 엣지"""
    topic_dir = WIKI / "Topics"
    if not topic_dir.exists():
        return []

    # 토픽별 프로젝트 목록 수집
    topic_projects: dict[str, list[str]] = {}
    for tp in sorted(topic_dir.glob("*.md")):
        text = tp.read_text("utf-8", errors="ignore")
        topic_name = tp.stem
        mentioned = []
        for linked in extract_wikilinks(text):
            # Summaries/ 아래 항목만 프로젝트로 취급
            stem = Path(linked).stem
            if stem in nodes and nodes[stem]["kind"] == "project":
                mentioned.append(stem)
        if mentioned:
            topic_projects[topic_name] = mentioned

    # 같은 토픽에 속한 프로젝트 쌍 → 엣지
    edges = []
    seen = set()
    for topic, projects in topic_projects.items():
        for i in range(len(projects)):
            for j in range(i + 1, len(projects)):
                a, b = projects[i], projects[j]
                key = tuple(sorted([a, b]))
                if key not in seen:
                    seen.add(key)
                    edges.append({
                        "source":   a,
                        "target":   b,
                        "relation": "공유개념",
                        "shared":   [topic],
                    })
                else:
                    # 기존 엣지에 shared 토픽 추가
                    for e in edges:
                        if tuple(sorted([e["source"], e["target"]])) == key:
                            if topic not in e["shared"]:
                                e["shared"].append(topic)
                            break
                log(f"토픽 엣지: {a} ↔ {b}  [{topic}]")

    return edges


# ── 4. 배포 관계 엣지 ────────────────────────────────────────────────────────

def collect_release_edges(nodes: dict) -> list[dict]:
    """release_ 접두어 → 원본 프로젝트와 '배포버전' 연결"""
    edges = []
    for nid, meta in nodes.items():
        if meta["kind"] != "project":
            continue
        if not nid.startswith("release_"):
            continue
        original = nid[len("release_"):]
        if original in nodes:
            edges.append({
                "source":   nid,
                "target":   original,
                "relation": "배포버전",
                "shared":   [],
            })
            log(f"배포 엣지: {nid} → {original}")
    return edges


# ── 5. 엣지 병합 (중복 제거 + shared 통합) ───────────────────────────────────

def merge_edges(edge_lists: list[list[dict]]) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for edges in edge_lists:
        for e in edges:
            key = (e["source"], e["target"], e["relation"])
            rev = (e["target"], e["source"], e["relation"])
            if key in merged:
                for s in e["shared"]:
                    if s not in merged[key]["shared"]:
                        merged[key]["shared"].append(s)
            elif rev in merged:
                for s in e["shared"]:
                    if s not in merged[rev]["shared"]:
                        merged[rev]["shared"].append(s)
            else:
                merged[key] = dict(e)
    return list(merged.values())


# ── 6. graph.json 저장 ───────────────────────────────────────────────────────

def save_graph_json(nodes: dict, edges: list[dict]):
    # home.html에서 사용하는 project 노드만 포함 (전체 노드 시 너무 큼)
    proj_ids = {nid for nid, m in nodes.items() if m["kind"] == "project"}
    proj_edges = [e for e in edges
                  if e["source"] in proj_ids and e["target"] in proj_ids]

    data = {
        "nodes":      [{"id": nid} for nid in sorted(proj_ids)],
        "links":      proj_edges,
        "generated":  datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(f"  ✅ graph.json — 노드 {len(data['nodes'])}개, 링크 {len(proj_edges)}개")


# ── 7. graph.html (D3.js 인터랙티브) ─────────────────────────────────────────

def save_graph_html(nodes: dict, edges: list[dict]):
    """self-contained D3 v7 force-directed graph"""

    # 전체 노드 사용 (Concepts/Entities 포함)
    KIND_COLOR = {
        "project": "#38bdf8",
        "concept": "#818cf8",
        "entity":  "#34d399",
        "topic":   "#fbbf24",
    }
    KIND_RADIUS = {"project": 14, "concept": 9, "entity": 9, "topic": 11}

    nodes_json = json.dumps([
        {
            "id":     nid,
            "kind":   m["kind"],
            "color":  KIND_COLOR.get(m["kind"], "#94a3b8"),
            "radius": KIND_RADIUS.get(m["kind"], 8),
        }
        for nid, m in nodes.items()
    ], ensure_ascii=False)

    links_json = json.dumps([
        {"source": e["source"], "target": e["target"],
         "relation": e["relation"], "shared": e.get("shared", [])}
        for e in edges
        if e["source"] in nodes and e["target"] in nodes
    ], ensure_ascii=False)

    RELATION_COLOR = {
        "공유개념": "#38bdf8",
        "참조":    "#818cf8",
        "배포버전": "#34d399",
    }
    rel_color_json = json.dumps(RELATION_COLOR, ensure_ascii=False)

    html = f"""<!DOCTYPE html><html lang="ko"><head>
<meta charset="UTF-8">
<title>Wiki 지식 그래프</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;overflow:hidden;}}
  #toolbar{{position:fixed;top:12px;left:12px;display:flex;gap:8px;z-index:10;flex-wrap:wrap;}}
  .btn{{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:6px 14px;
        color:#e2e8f0;font-size:12px;cursor:pointer;transition:border-color .2s;}}
  .btn:hover{{border-color:#38bdf8;}}
  #legend{{position:fixed;bottom:16px;left:16px;background:#1e293b;
           border:1px solid #334155;border-radius:8px;padding:12px 16px;font-size:12px;}}
  .leg-item{{display:flex;align-items:center;gap:8px;margin:4px 0;}}
  .leg-dot{{width:12px;height:12px;border-radius:50%;}}
  #info{{position:fixed;top:12px;right:12px;background:#1e293b;border:1px solid #334155;
         border-radius:8px;padding:12px 16px;font-size:12px;max-width:260px;min-width:180px;
         display:none;}}
  #info h3{{color:#38bdf8;margin:0 0 8px;font-size:14px;}}
  .info-row{{color:#94a3b8;margin:3px 0;}}
  .info-row span{{color:#e2e8f0;}}
  #count{{position:fixed;top:12px;left:50%;transform:translateX(-50%);
          background:#1e293b;border:1px solid #334155;border-radius:6px;
          padding:6px 16px;font-size:12px;color:#94a3b8;}}
  svg .link{{stroke-opacity:0.5;}}
  svg .node{{cursor:pointer;}}
  svg .label{{font-size:11px;fill:#e2e8f0;pointer-events:none;}}
</style>
</head><body>
<div id="toolbar">
  <button class="btn" onclick="resetZoom()">⟳ 리셋</button>
  <button class="btn" onclick="toggleLabels()">🏷 라벨</button>
  <button class="btn" id="filterBtn" onclick="filterProjects()">📁 프로젝트만</button>
</div>
<div id="count">로딩 중...</div>
<div id="legend">
  <div style="font-weight:600;margin-bottom:8px;color:#94a3b8;">노드 종류</div>
  <div class="leg-item"><div class="leg-dot" style="background:#38bdf8"></div>프로젝트</div>
  <div class="leg-item"><div class="leg-dot" style="background:#818cf8"></div>개념</div>
  <div class="leg-item"><div class="leg-dot" style="background:#34d399"></div>엔티티</div>
  <div class="leg-item"><div class="leg-dot" style="background:#fbbf24"></div>토픽</div>
  <div style="margin-top:10px;font-weight:600;margin-bottom:8px;color:#94a3b8;">엣지 종류</div>
  <div class="leg-item"><div style="width:24px;height:2px;background:#38bdf8"></div>공유개념</div>
  <div class="leg-item"><div style="width:24px;height:2px;background:#818cf8"></div>참조</div>
  <div class="leg-item"><div style="width:24px;height:2px;background:#34d399"></div>배포버전</div>
</div>
<div id="info"><h3 id="info-name"></h3>
  <div class="info-row">종류: <span id="info-kind"></span></div>
  <div class="info-row">연결: <span id="info-degree"></span>개</div>
  <div id="info-shared"></div>
</div>
<svg id="svg"></svg>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
const RAW_NODES = {nodes_json};
const RAW_LINKS = {links_json};
const REL_COLOR = {rel_color_json};

let showLabels = true;
let filterMode = false;
let simulation, svg, g, link, node, label, zoom;

function init(nodesData, linksData) {{
  const W = window.innerWidth, H = window.innerHeight;
  d3.select("#svg").selectAll("*").remove();

  svg = d3.select("#svg").attr("width", W).attr("height", H);
  zoom = d3.zoom().scaleExtent([0.2, 4])
    .on("zoom", e => g.attr("transform", e.transform));
  svg.call(zoom);
  g = svg.append("g");

  const nodeMap = new Map(nodesData.map(d => [d.id, d]));
  const links = linksData.map(d => ({{
    ...d,
    source: nodeMap.get(d.source) || d.source,
    target: nodeMap.get(d.target) || d.target,
  }}));

  // Degree
  const degree = new Map();
  nodesData.forEach(n => degree.set(n.id, 0));
  links.forEach(l => {{
    const s = typeof l.source === "object" ? l.source.id : l.source;
    const t = typeof l.target === "object" ? l.target.id : l.target;
    degree.set(s, (degree.get(s) || 0) + 1);
    degree.set(t, (degree.get(t) || 0) + 1);
  }});

  document.getElementById("count").textContent =
    `노드 ${{nodesData.length}}개 · 링크 ${{links.length}}개`;

  simulation = d3.forceSimulation(nodesData)
    .force("link", d3.forceLink(links).id(d => d.id).distance(d => {{
      const s = typeof d.source === "object" ? d.source : nodesData.find(n=>n.id===d.source);
      const t = typeof d.target === "object" ? d.target : nodesData.find(n=>n.id===d.target);
      if (s && t && s.kind==="project" && t.kind==="project") return 120;
      return 80;
    }}))
    .force("charge", d3.forceManyBody().strength(d => d.kind==="project" ? -300 : -120))
    .force("center", d3.forceCenter(W/2, H/2))
    .force("collision", d3.forceCollide().radius(d => d.radius + 6));

  link = g.append("g").attr("class","links")
    .selectAll("line").data(links).join("line")
    .attr("class","link")
    .attr("stroke", d => REL_COLOR[d.relation] || "#475569")
    .attr("stroke-width", d => d.relation==="공유개념" ? 2 : 1.5)
    .attr("stroke-dasharray", d => d.relation==="참조" ? "4,3" : null);

  node = g.append("g").attr("class","nodes")
    .selectAll("circle").data(nodesData).join("circle")
    .attr("class","node")
    .attr("r", d => d.radius)
    .attr("fill", d => d.color)
    .attr("stroke", "#0f172a").attr("stroke-width", 2)
    .on("click", (event, d) => showInfo(d, degree.get(d.id)||0, links))
    .on("mouseover", function(event, d) {{
      d3.select(this).attr("stroke","#fff").attr("stroke-width",3);
    }})
    .on("mouseout", function(event, d) {{
      d3.select(this).attr("stroke","#0f172a").attr("stroke-width",2);
    }})
    .call(d3.drag()
      .on("start", (e,d) => {{ if(!e.active) simulation.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on("drag",  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on("end",   (e,d) => {{ if(!e.active) simulation.alphaTarget(0); d.fx=null; d.fy=null; }}));

  label = g.append("g").attr("class","labels")
    .selectAll("text").data(nodesData).join("text")
    .attr("class","label")
    .attr("dy","0.35em")
    .attr("text-anchor","middle")
    .attr("y", d => d.radius + 12)
    .text(d => d.id.length > 16 ? d.id.slice(0,14)+"…" : d.id)
    .style("display", showLabels ? null : "none");

  simulation.on("tick", () => {{
    link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
        .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    node.attr("cx",d=>d.x).attr("cy",d=>d.y);
    label.attr("x",d=>d.x).attr("y",d=>d.y + d.radius + 12);
  }});
}}

function showInfo(d, deg, links) {{
  document.getElementById("info").style.display = "block";
  document.getElementById("info-name").textContent = d.id;
  document.getElementById("info-kind").textContent =
    {{project:"프로젝트",concept:"개념",entity:"엔티티",topic:"토픽"}}[d.kind]||d.kind;
  document.getElementById("info-degree").textContent = deg;
  const related = links
    .filter(l => (l.source.id||l.source)===d.id || (l.target.id||l.target)===d.id)
    .map(l => {{
      const other = (l.source.id||l.source)===d.id ? (l.target.id||l.target) : (l.source.id||l.source);
      const shared = l.shared&&l.shared.length ? " ("+l.shared.join(",")+")":"";
      return `<div class="info-row">→ <span>${{other}}</span>${{shared}}</div>`;
    }});
  document.getElementById("info-shared").innerHTML = related.slice(0,6).join("");
}}

function resetZoom() {{
  svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
}}
function toggleLabels() {{
  showLabels = !showLabels;
  label.style("display", showLabels ? null : "none");
}}
function filterProjects() {{
  filterMode = !filterMode;
  document.getElementById("filterBtn").textContent = filterMode ? "🌐 전체 보기" : "📁 프로젝트만";
  if (filterMode) {{
    const projNodes = RAW_NODES.filter(n => n.kind==="project");
    const projIds = new Set(projNodes.map(n=>n.id));
    const projLinks = RAW_LINKS.filter(l => projIds.has(l.source) && projIds.has(l.target));
    init(projNodes, projLinks);
  }} else {{
    init(RAW_NODES, RAW_LINKS);
  }}
}}

svg.on("click", (e) => {{
  if (e.target.tagName === "svg" || e.target.tagName === "g") {{
    document.getElementById("info").style.display = "none";
  }}
}});

window.addEventListener("resize", () => {{
  d3.select("#svg").attr("width", window.innerWidth).attr("height", window.innerHeight);
}});

init(RAW_NODES, RAW_LINKS);
</script>
</body></html>"""

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"  ✅ graph.html — D3.js 인터랙티브 시각화 생성")


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    print("🕸️  Wiki 지식 그래프 재생성 중...")

    # 노드 수집
    nodes = collect_nodes()
    print(f"  노드: {len(nodes)}개 "
          f"(프로젝트 {sum(1 for m in nodes.values() if m['kind']=='project')}개"
          f" | 개념 {sum(1 for m in nodes.values() if m['kind']=='concept')}개"
          f" | 엔티티 {sum(1 for m in nodes.values() if m['kind']=='entity')}개"
          f" | 토픽 {sum(1 for m in nodes.values() if m['kind']=='topic')}개)")

    # 엣지 수집
    topic_edges   = collect_topic_edges(nodes)
    wikilink_edges = collect_wikilink_edges(nodes)
    release_edges = collect_release_edges(nodes)

    all_edges = merge_edges([topic_edges, wikilink_edges, release_edges])

    edge_by_rel: dict[str, int] = {}
    for e in all_edges:
        edge_by_rel[e["relation"]] = edge_by_rel.get(e["relation"], 0) + 1
    edge_summary = " | ".join(f"{r} {c}개" for r, c in sorted(edge_by_rel.items()))
    print(f"  엣지: {len(all_edges)}개 ({edge_summary})")

    # 저장
    save_graph_json(nodes, all_edges)
    save_graph_html(nodes, all_edges)

    print(f"✅ 그래프 재생성 완료 → Wiki/GraphData/")


if __name__ == "__main__":
    main()
