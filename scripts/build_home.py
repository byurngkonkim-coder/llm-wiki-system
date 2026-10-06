#!/usr/bin/env python3
"""
build_home.py — LLM Wiki home.html 재생성기
============================================
Wiki/*.md 파일을 읽어 Wiki/home.html 을 재생성합니다.

P1-1: 7일 최근 변경 섹션 (파일 mtime 기반)
P1-2: 미해결 이슈 카운트 (BUG: / TODO: 태그)

실행:
    python build_home.py
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent.parent
WIKI = BASE / "Wiki"
OUT  = WIKI / "home.html"


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def parse_md(p: Path) -> dict:
    """frontmatter + 첫 설명 + H2 섹션 목록 추출"""
    txt = p.read_text("utf-8", errors="ignore")
    fm, body = {}, txt

    if txt.startswith("---"):
        end = txt.find("---", 3)
        if end > 0:
            for ln in txt[3:end].splitlines():
                k, _, v = ln.partition(":")
                if k.strip():
                    fm[k.strip()] = v.strip()
            body = txt[end + 3:]

    # 태그 파싱
    tags = [t for t in re.findall(r"[\w가-힣.\-+#]+", fm.get("tags", ""))
            if t not in ("tags", "source", "created", "updated", "true", "false")]

    # 제목 (첫 H1)
    title = p.stem
    for ln in body.splitlines():
        if ln.startswith("# "):
            title = ln[2:].strip()
            break

    # H2 섹션 목록
    sections = [ln[3:].strip() for ln in body.splitlines() if ln.startswith("## ")]

    # 첫 설명 (15자 이상의 의미 있는 줄)
    desc = ""
    for ln in body.splitlines():
        s = ln.strip().lstrip(">").strip()
        s = re.sub(r"\[!\w+\]", "", s).strip()
        if s.startswith("**") and s.endswith("**"):
            continue
        if s.startswith("- ") or s.startswith("* "):
            s = s[2:]
        if len(s) > 15 and not s.startswith("#") and s not in ("---", "```"):
            desc = s[:120]
            break

    return {
        "stem": p.stem,
        "title": title,
        "desc": desc,
        "tags": tags,
        "sections": sections,
        "source": fm.get("source", "-"),
        "created": fm.get("created",
                          datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")),
    }


def load_section(sub: str) -> list:
    d = WIKI / sub
    if not d.exists():
        return []
    return [parse_md(p) for p in sorted(d.glob("*.md"))]


# ── P1-1: 7일 최근 변경 ───────────────────────────────────────────────────────

def get_recent(days: int = 7) -> list:
    """WIKI 내 최근 N일 변경된 .md 파일 목록 (mtime 내림차순)"""
    cutoff = datetime.now() - timedelta(days=days)
    items = []
    for p in WIKI.rglob("*.md"):
        mt = datetime.fromtimestamp(p.stat().st_mtime)
        if mt >= cutoff:
            rel = p.relative_to(WIKI)
            parts = rel.parts
            items.append({
                "name": p.stem,
                "rel":  str(rel).replace("\\", "/"),
                "section": parts[0] if len(parts) > 1 else "root",
                "mtime_str": mt.strftime("%m-%d %H:%M"),
                "mtime_ts":  mt.timestamp(),
            })
    return sorted(items, key=lambda x: x["mtime_ts"], reverse=True)


# ── P1-2: 미해결 이슈 스캔 ────────────────────────────────────────────────────

def scan_issues() -> list:
    """BUG / TODO 태그가 있는 줄 수집"""
    issues = []
    pat = re.compile(r"\b(BUG|TODO)\b[-:\s]", re.IGNORECASE)
    for p in sorted(WIKI.rglob("*.md")):
        rel = str(p.relative_to(WIKI)).replace("\\", "/")
        for ln in p.read_text("utf-8", errors="ignore").splitlines():
            m = pat.search(ln)
            if m:
                issues.append({
                    "file": p.stem,
                    "rel":  rel,
                    "kind": m.group(1).upper(),
                    "text": ln.strip()[:120],
                })
    return issues


# ── 그래프 로드 ───────────────────────────────────────────────────────────────

def load_graph() -> list:
    f = WIKI / "GraphData" / "graph.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text("utf-8"))
        return d.get("links", d.get("edges", []))
    except Exception:
        return []


# ── HTML 부품 ─────────────────────────────────────────────────────────────────

def tags_html(tags: list) -> str:
    return "".join(f'<span class="tag">{esc(t)}</span>' for t in tags[:5])


def proj_card(item: dict) -> str:
    return (
        f'<div class="card" onclick="openMd(\'Summaries/{esc(item["stem"])}.md\')">'
        f'<div class="card-title">{esc(item["stem"])}</div>'
        f'<div class="card-desc">{esc(item["desc"])}</div>'
        f'<div class="card-tags">{tags_html(item["tags"])}</div></div>\n'
    )


def logic_card(item: dict) -> str:
    secs = "".join(f'<li class="logic-item">{esc(s)}</li>' for s in item["sections"][:5])
    if not secs:
        secs = '<span class="logic-empty">섹션 정보 없음</span>'
    return (
        f'<div class="card" onclick="openMd(\'Summaries/{esc(item["stem"])}.md\')">'
        f'<div class="card-title">{esc(item["stem"])}</div>'
        f'<div class="card-tags" style="margin-bottom:8px">{tags_html(item["tags"])}</div>'
        f'<ul class="logic-list">{secs}</ul></div>\n'
    )


def wiki_list_item(item: dict, subdir: str) -> str:
    return (
        f'<li class="list-item" onclick="openMd(\'{subdir}/{esc(item["stem"])}.md\')">'
        f'<span class="li-name">{esc(item["stem"])}</span>'
        f'<span class="li-desc">{esc(item["desc"])}</span></li>\n'
    )


# ── HTML 전체 생성 ────────────────────────────────────────────────────────────

CSS = (
    ":root{--bg:#0f172a;--surface:#1e293b;--surface2:#273449;--accent:#38bdf8;"
    "--accent2:#818cf8;--text:#e2e8f0;--muted:#94a3b8;--border:#334155;"
    "--tag:#0ea5e9;--green:#34d399;--yellow:#fbbf24;--red:#f87171;}"
    "*{box-sizing:border-box;margin:0;padding:0;}"
    "body{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh;}"
    "header{background:var(--surface);border-bottom:1px solid var(--border);padding:16px 24px;"
    "display:flex;align-items:center;justify-content:space-between;}"
    "header h1{font-size:18px;color:var(--accent);}"
    ".updated{font-size:12px;color:var(--muted);}"
    ".stats{display:flex;gap:12px;padding:14px 24px;background:var(--surface2);"
    "border-bottom:1px solid var(--border);flex-wrap:wrap;}"
    ".stat{background:var(--surface);border:1px solid var(--border);border-radius:8px;"
    "padding:8px 16px;font-size:13px;cursor:pointer;transition:border-color .2s;}"
    ".stat:hover{border-color:var(--accent);}"
    ".stat-num{font-size:22px;font-weight:700;color:var(--accent);display:block;}"
    ".stat-label{color:var(--muted);font-size:11px;}"
    ".tabs{display:flex;background:var(--surface);border-bottom:1px solid var(--border);"
    "padding:0 24px;gap:4px;overflow-x:auto;}"
    ".tab{padding:12px 16px;cursor:pointer;border-bottom:2px solid transparent;"
    "color:var(--muted);font-size:13px;white-space:nowrap;transition:all .2s;}"
    ".tab:hover{color:var(--text);}"
    ".tab.active{color:var(--accent);border-bottom-color:var(--accent);}"
    ".badge{background:var(--accent);color:#000;border-radius:10px;padding:1px 6px;"
    "font-size:10px;font-weight:700;margin-left:5px;}"
    ".badge-warn{background:var(--yellow);color:#000;border-radius:10px;padding:1px 6px;"
    "font-size:10px;font-weight:700;margin-left:5px;}"
    ".panel{display:none;padding:24px;max-width:1400px;margin:0 auto;}"
    ".panel.active{display:block;}"
    ".search-box{width:100%;padding:10px 16px;background:var(--surface2);"
    "border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:14px;"
    "margin-bottom:20px;outline:none;}"
    ".search-box:focus{border-color:var(--accent);}"
    ".card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;}"
    ".card{background:var(--surface);border:1px solid var(--border);border-radius:10px;"
    "padding:16px;cursor:pointer;transition:all .2s;}"
    ".card:hover{border-color:var(--accent);transform:translateY(-2px);"
    "box-shadow:0 4px 20px rgba(56,189,248,.15);}"
    ".card-title{font-size:14px;font-weight:600;margin-bottom:6px;}"
    ".card-desc{font-size:12px;color:var(--muted);margin-bottom:10px;line-height:1.5;min-height:36px;}"
    ".card-tags{display:flex;gap:4px;flex-wrap:wrap;}"
    ".tag{background:rgba(14,165,233,.15);color:var(--tag);border-radius:4px;padding:2px 8px;font-size:11px;}"
    ".wiki-list{list-style:none;display:flex;flex-direction:column;gap:8px;}"
    ".list-item{background:var(--surface);border:1px solid var(--border);border-radius:8px;"
    "padding:12px 16px;cursor:pointer;display:flex;align-items:center;gap:12px;transition:all .2s;}"
    ".list-item:hover{border-color:var(--accent2);}"
    ".li-name{font-size:14px;font-weight:600;min-width:200px;color:var(--accent2);}"
    ".li-desc{font-size:12px;color:var(--muted);}"
    ".logic-list{margin-top:8px;list-style:none;display:flex;flex-direction:column;gap:4px;}"
    ".logic-item{font-size:12px;color:var(--text);padding:4px 8px;background:var(--surface2);"
    "border-radius:4px;border-left:2px solid var(--accent2);}"
    ".logic-empty{font-size:11px;color:var(--muted);margin-top:8px;font-style:italic;}"
    ".log-wrap{max-width:860px;}"
    ".log-date{font-size:16px;font-weight:700;color:var(--yellow);margin:24px 0 8px;"
    "padding-bottom:6px;border-bottom:1px solid var(--border);}"
    ".log-section{font-size:13px;font-weight:600;color:var(--accent2);margin:14px 0 6px;}"
    ".log-item{font-size:13px;color:var(--text);padding:4px 0 4px 12px;"
    "border-left:2px solid var(--border);margin-left:4px;line-height:1.6;}"
    ".log-item strong{color:var(--accent);}"
    ".log-item code{background:var(--surface2);padding:1px 5px;border-radius:3px;"
    "font-size:11px;color:var(--green);}"
    ".log-hr{border:none;border-top:1px solid var(--border);margin:20px 0;}"
    ".log-p{font-size:13px;color:var(--muted);margin:6px 0;}"
    ".src-table{width:100%;border-collapse:collapse;font-size:13px;}"
    ".src-table th{background:var(--surface2);color:var(--muted);padding:10px 14px;"
    "text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;}"
    ".src-table td{padding:10px 14px;border-bottom:1px solid var(--border);vertical-align:top;}"
    ".src-table tr:hover td{background:var(--surface2);}"
    ".src-name{color:var(--accent2);font-weight:600;}"
    ".src-path{font-size:11px;color:var(--muted);font-family:monospace;"
    "max-width:380px;word-break:break-all;}"
    ".src-date{font-size:12px;color:var(--muted);white-space:nowrap;}"
    ".gtable{width:100%;border-collapse:collapse;font-size:13px;}"
    ".gtable th{background:var(--surface2);color:var(--muted);padding:10px 14px;"
    "text-align:left;border-bottom:1px solid var(--border);}"
    ".gtable td{padding:10px 14px;border-bottom:1px solid var(--border);}"
    ".gtable tr:hover td{background:var(--surface2);}"
    ".rel{background:rgba(129,140,248,.2);color:var(--accent2);border-radius:4px;"
    "padding:2px 8px;font-size:11px;}"
    ".sec-title{font-size:12px;color:var(--muted);margin:0 0 14px;"
    "text-transform:uppercase;letter-spacing:.5px;}"
    ".hidden{display:none!important;}"
    # P1 추가 스타일
    ".issue-bug{background:rgba(248,113,113,.2);color:var(--red);"
    "border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;min-width:44px;text-align:center;}"
    ".issue-todo{background:rgba(251,191,36,.2);color:var(--yellow);"
    "border-radius:4px;padding:2px 8px;font-size:11px;font-weight:700;min-width:44px;text-align:center;}"
    ".ri-mtime{margin-left:auto;font-size:11px;color:var(--muted);white-space:nowrap;}"
)

JS = (
    "function switchTab(n){"
    "document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('active');});"
    "document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});"
    "var tab=document.getElementById('tab-'+n);"
    "var panel=document.getElementById('panel-'+n);"
    "if(tab)tab.classList.add('active');"
    "if(panel)panel.classList.add('active');}"
    "function openMd(p){"
    "var v='개발프로그램';"
    "var u='obsidian://open?vault='+encodeURIComponent(v)+'&file='+encodeURIComponent('Wiki/'+p);"
    "window.open(u,'_self');}"
    "function filterCards(t){"
    "var q=document.getElementById('search-'+t).value.toLowerCase();"
    "document.querySelectorAll('#grid-'+t+' .card').forEach(function(c){"
    "c.classList.toggle('hidden',q.length>0&&!c.innerText.toLowerCase().includes(q));});}"
    "function filterList(t){"
    "var q=document.getElementById('search-'+t).value.toLowerCase();"
    "document.querySelectorAll('#list-'+t+' .list-item').forEach(function(li){"
    "li.classList.toggle('hidden',q.length>0&&!li.innerText.toLowerCase().includes(q));});}"
    "function filterTable(t){"
    "var q=document.getElementById('search-'+t).value.toLowerCase();"
    "document.querySelectorAll('#table-'+t+' tbody tr').forEach(function(tr){"
    "tr.classList.toggle('hidden',q.length>0&&!tr.innerText.toLowerCase().includes(q));});}"
)


def build_html(projects, concepts, entities, topics, recent, issues, graph):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    n_proj   = len(projects)
    n_conc   = len(concepts)
    n_ent    = len(entities)
    n_top    = len(topics)
    n_graph  = len(graph)
    n_src    = n_proj + n_conc + n_ent + n_top
    n_recent = len(recent)
    n_issues = len(issues)

    # ── 프로젝트 패널 ──
    proj_cards  = "".join(proj_card(p) for p in projects)
    logic_cards = "".join(logic_card(p) for p in projects)

    # ── 리스트 패널 ──
    conc_items = "".join(wiki_list_item(c, "Concepts") for c in concepts)
    ent_items  = "".join(wiki_list_item(e, "Entities") for e in entities)
    top_items  = "".join(wiki_list_item(t, "Topics")   for t in topics)

    # ── 출처 테이블 ──
    all_typed = (
        [(p, "Summaries") for p in projects] +
        [(c, "Concepts")  for c in concepts] +
        [(e, "Entities")  for e in entities] +
        [(t, "Topics")    for t in topics]
    )
    src_rows = ""
    for item, sec in all_typed:
        src_short = item["source"][:52] + ("..." if len(item["source"]) > 52 else "")
        src_rows += (
            f'<tr onclick="openMd(\'{sec}/{esc(item["stem"])}.md\')" style="cursor:pointer;">'
            f'<td><span class="src-name">{esc(item["stem"])}</span></td>'
            f'<td class="src-path" title="{esc(item["source"])}">{esc(src_short)}</td>'
            f'<td class="src-date">{esc(item["created"])}</td>'
            f'<td><span class="tag">{sec}</span></td></tr>\n'
        )

    # ── 그래프 테이블 ──
    graph_rows = ""
    for e in graph:
        shared = ", ".join(e.get("shared", [])) if isinstance(e.get("shared"), list) else str(e.get("shared", ""))
        graph_rows += (
            f'<tr><td>{esc(str(e.get("source","?")))}</td>'
            f'<td><span class="rel">{esc(str(e.get("relation","공유개념")))}</span></td>'
            f'<td>{esc(str(e.get("target","?")))}</td>'
            f'<td>{esc(shared)}</td></tr>\n'
        )
    if not graph_rows:
        graph_rows = '<tr><td colspan="4" style="color:var(--muted);padding:20px;">그래프 데이터 없음 — graphify_run.py 를 실행하세요</td></tr>'

    # ── P1-1: 최근 변경 패널 ──
    if recent:
        recent_rows = ""
        for r in recent:
            recent_rows += (
                f'<li class="list-item" onclick="openMd(\'{esc(r["rel"])}\')">'
                f'<span class="li-name">{esc(r["name"])}</span>'
                f'<span class="tag">{esc(r["section"])}</span>'
                f'<span class="ri-mtime">{esc(r["mtime_str"])}</span>'
                f'</li>\n'
            )
    else:
        recent_rows = '<li style="padding:20px;color:var(--muted);font-size:13px;">최근 7일 내 변경 없음</li>'

    # ── P1-2: 이슈 패널 ──
    if issues:
        issue_rows = ""
        for iss in issues:
            badge_cls = "issue-bug" if iss["kind"] == "BUG" else "issue-todo"
            issue_rows += (
                f'<li class="list-item" onclick="openMd(\'{esc(iss["rel"])}\')">'
                f'<span class="{badge_cls}">{iss["kind"]}</span>'
                f'<span class="li-name" style="min-width:160px">{esc(iss["file"])}</span>'
                f'<span class="li-desc">{esc(iss["text"])}</span>'
                f'</li>\n'
            )
    else:
        issue_rows = '<li style="padding:20px;color:var(--green);font-size:13px;">미해결 이슈 없음 ✅</li>'

    # 이슈 스탯 색상
    issue_num_color = "var(--yellow)" if n_issues > 0 else "var(--green)"
    issue_badge = f'<span class="badge-warn">{n_issues}</span>' if n_issues > 0 else ""

    return f"""<!DOCTYPE html><html lang="ko"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wiki Home</title>
<style>{CSS}</style>
</head><body>
<header>
<h1>&#x1F9E0; 개발프로그램 LLM Wiki</h1>
<span class="updated">마지막 갱신: {now_str}</span>
</header>
<div class="stats">
<div class="stat" onclick="switchTab('projects')"><span class="stat-num">{n_proj}</span><span class="stat-label">프로젝트</span></div>
<div class="stat" onclick="switchTab('concepts')"><span class="stat-num">{n_conc}</span><span class="stat-label">핵심 개념</span></div>
<div class="stat" onclick="switchTab('entities')"><span class="stat-num">{n_ent}</span><span class="stat-label">엔티티</span></div>
<div class="stat" onclick="switchTab('topics')"><span class="stat-num">{n_top}</span><span class="stat-label">토픽</span></div>
<div class="stat" onclick="switchTab('graph')"><span class="stat-num">{n_graph}</span><span class="stat-label">연결 관계</span></div>
<div class="stat" onclick="switchTab('sources')"><span class="stat-num">{n_src}</span><span class="stat-label">출처 추적</span></div>
<div class="stat" onclick="switchTab('recent')"><span class="stat-num" style="color:var(--green)">{n_recent}</span><span class="stat-label">최근 변경</span></div>
<div class="stat" onclick="switchTab('issues')"><span class="stat-num" style="color:{issue_num_color}">{n_issues}</span><span class="stat-label">미해결 이슈</span></div>
</div>
<div class="tabs">
<div class="tab active" id="tab-projects" onclick="switchTab('projects')">&#x1F4C1; 프로젝트<span class="badge">{n_proj}</span></div>
<div class="tab" id="tab-logic" onclick="switchTab('logic')">&#x2699; 기능/로직<span class="badge">{n_proj}</span></div>
<div class="tab" id="tab-concepts" onclick="switchTab('concepts')">&#x1F9E0; 개념<span class="badge">{n_conc}</span></div>
<div class="tab" id="tab-entities" onclick="switchTab('entities')">&#x1F527; 엔티티<span class="badge">{n_ent}</span></div>
<div class="tab" id="tab-topics" onclick="switchTab('topics')">&#x1F4CB; 토픽<span class="badge">{n_top}</span></div>
<div class="tab" id="tab-sources" onclick="switchTab('sources')">&#x1F517; 출처 추적<span class="badge">{n_src}</span></div>
<div class="tab" id="tab-log" onclick="switchTab('log')">&#x1F4DD; 변경 이력</div>
<div class="tab" id="tab-graph" onclick="switchTab('graph')">&#x1F578; 지식 그래프<span class="badge">{n_graph}</span></div>
<div class="tab" id="tab-recent" onclick="switchTab('recent')">&#x1F514; 최근 변경<span class="badge" style="background:var(--green);color:#000">{n_recent}</span></div>
<div class="tab" id="tab-issues" onclick="switchTab('issues')">&#x26A0; 미해결{issue_badge}</div>
</div>
<div class="panel active" id="panel-projects">
<input class="search-box" id="search-projects" placeholder="프로젝트 검색..." oninput="filterCards('projects')">
<div class="card-grid" id="grid-projects">{proj_cards}</div>
</div>
<div class="panel" id="panel-logic">
<p class="sec-title">각 프로젝트의 주요 기능 및 섹션</p>
<input class="search-box" id="search-logic" placeholder="기능/섹션 검색..." oninput="filterCards('logic')">
<div class="card-grid" id="grid-logic">{logic_cards}</div>
</div>
<div class="panel" id="panel-concepts">
<input class="search-box" id="search-concepts" placeholder="개념 검색..." oninput="filterList('concepts')">
<ul class="wiki-list" id="list-concepts">{conc_items}</ul>
</div>
<div class="panel" id="panel-entities">
<input class="search-box" id="search-entities" placeholder="엔티티 검색..." oninput="filterList('entities')">
<ul class="wiki-list" id="list-entities">{ent_items}</ul>
</div>
<div class="panel" id="panel-topics">
<input class="search-box" id="search-topics" placeholder="토픽 검색..." oninput="filterList('topics')">
<ul class="wiki-list" id="list-topics">{top_items}</ul>
</div>
<div class="panel" id="panel-sources">
<p class="sec-title">모든 Wiki 파일 — 원본 소스 역추적 (클릭시 Obsidian)</p>
<input class="search-box" id="search-sources" placeholder="파일명/출처 검색..." oninput="filterTable('sources')">
<table class="src-table" id="table-sources"><thead><tr><th>Wiki File</th><th>Source</th><th>Created</th><th>Type</th></tr></thead><tbody>
{src_rows}</tbody></table>
</div>
<div class="panel" id="panel-log">
<div style="display:flex;gap:12px;margin-bottom:20px;">
<div class="card" onclick="openMd('hot.md')" style="flex:1;cursor:pointer;"><div class="card-title">&#x1F525; Hot — 현재 작업 메모리</div><div class="card-desc">진행 중 작업 · 다음 단계 · 미해결 이슈</div></div>
<div class="card" onclick="openMd('log.md')" style="flex:1;cursor:pointer;"><div class="card-title">&#x1F4CB; Log — Obsidian에서 편집</div><div class="card-desc">전체 log.md를 Obsidian에서 열기</div></div>
</div>
<div class="log-wrap"><p class="log-p">로그는 <code>Wiki/log.md</code> 에서 직접 편집하고, wiki_refresh.bat 실행 시 홈 화면이 갱신됩니다.</p></div>
</div>
<div class="panel" id="panel-graph">
<p class="sec-title">프로젝트 간 연결 관계</p>
<table class="gtable"><thead><tr><th>Project A</th><th>Relation</th><th>Project B</th><th>Shared</th></tr></thead><tbody>
{graph_rows}</tbody></table>
<div style="text-align:center;margin-top:20px;"><button onclick="window.open('GraphData/graph.html')" style="background:var(--accent);color:#000;border:none;border-radius:8px;padding:10px 24px;font-size:14px;cursor:pointer;font-weight:600;">&#x1F578; 인터랙티브 그래프 열기</button></div>
</div>
<div class="panel" id="panel-recent">
<p class="sec-title">최근 7일 내 변경된 Wiki 파일 ({n_recent}개)</p>
<ul class="wiki-list" id="list-recent">
{recent_rows}</ul>
</div>
<div class="panel" id="panel-issues">
<p class="sec-title">미해결 이슈 — BUG / TODO 태그 ({n_issues}개)</p>
<ul class="wiki-list" id="list-issues">
{issue_rows}</ul>
</div>
<script>{JS}</script>
</body></html>"""


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    print("📊 Wiki home.html 생성 중...")
    projects = load_section("Summaries")
    concepts = load_section("Concepts")
    entities = load_section("Entities")
    topics   = load_section("Topics")
    recent   = get_recent(7)
    issues   = scan_issues()
    graph    = load_graph()

    html = build_html(projects, concepts, entities, topics, recent, issues, graph)
    OUT.write_text(html, encoding="utf-8")

    print(f"✅ {OUT} 생성 완료")
    print(f"   프로젝트 {len(projects)}개 | 개념 {len(concepts)}개 | 엔티티 {len(entities)}개 | 토픽 {len(topics)}개")
    print(f"   최근 변경 {len(recent)}개 | 미해결 이슈 {len(issues)}개 (BUG/TODO)")


if __name__ == "__main__":
    main()
