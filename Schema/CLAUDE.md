# LLM_Wiki시스템 — 프로젝트 AI 운영 지침

> **Karpathy LLM Wiki 사상 + Graphify AST 분석을 결합한 나만의 세컨드 브레인 자동화 시스템**

---

## 프로젝트 목적

9개 개발 프로젝트의 소스코드·문서를 자동으로 분석·요약하여 Obsidian 기반 지식 저장소(Wiki)로 구조화한다.
RAG의 단기 기억 상실(Amnesia)을 극복하고, 지식을 미리 컴파일하여 영구 저장소로 관리한다.

---

## 폴더 구조

```
Raw/LLM_Wiki시스템/
├── scripts/                       ← 핵심 Python 자동화 스크립트
│   ├── ai_router.py               ← Ollama/Claude API 라우팅 모듈
│   ├── ingest.py                  ← Raw/ → Wiki/Summaries/ 자동 생성
│   ├── build_graph.py             ← Wiki 링크 → graph.json/html 생성
│   ├── build_home.py              ← Wiki → home.html 대시보드 생성
│   ├── graphify_run.py            ← AST 기반 코드 구조 분석 (0 토큰)
│   ├── graphify_context.py        ← 그래프 컨텍스트 조회 유틸
│   └── watch_wiki.py              ← watchdog 기반 파일 변경 감지 데몬
├── start.bat                      ← 원클릭 전체 갱신 (사용자 진입점)
├── ai_config.json                 ← AI 엔진 설정 (Ollama 우선, Claude 폴백)
├── CLAUDE.md                      ← 전체 운영 지침 (컨트롤 타워)
├── Wiki/                          ← AI 생성 위키 출력
└── Schema/
    └── CLAUDE.md                  ← 현재 파일
```

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| AI 엔진 (1순위) | Ollama (gemma2:2b) — 로컬, 무료 |
| AI 엔진 (2순위) | Claude API (claude-haiku-4-5-20251001) — 폴백 |
| AST 분석 | graphifyy (pip) — 토큰 0원 |
| 지식 그래프 | networkx + D3.js |
| 파일 감지 | watchdog |
| 문서 뷰어 | Obsidian (Dataview + Templater 플러그인) |
| 언어 | Python 3.x |
| 운영 환경 | Windows 11 + PowerShell |

---

## 핵심 스크립트 설명

### ai_router.py
- Ollama(localhost:11434) 우선 호출 → 실패 시 Claude API 자동 폴백
- `ask_ai(task, prompt)` 인터페이스 통일
- 태스크별 엔진 지정: summarize_doc/code → Ollama, complex_reasoning → Claude

### ingest.py
- Raw/ 폴더 9개 프로젝트 스캔
- 파일 스택(TypeScript/Python/SQL 등) 자동 감지
- Ollama로 프로젝트별 요약 생성 → Wiki/Summaries/{프로젝트명}.md 저장

### build_graph.py
- Wiki/*.md 파일의 `[[링크]]` 파싱
- 공유 토픽·배포버전 관계 분석
- D3.js 인터랙티브 graph.html 생성 (필터·라벨 토글)

### build_home.py
- Wiki 전체 마크다운 → home.html 대시보드
- 탭: 프로젝트 요약 / 개념 / 엔티티 / 토픽 / 최근 7일 변경 / 미해결 이슈

### graphify_run.py
- AST(추상 구문 트리) 기반 코드 구조 추출 — AI 토큰 0원
- 9개 프로젝트 → Wiki/GraphData/{프로젝트}/graph.json + graph.html
- 허브 노드, 커뮤니티 클러스터, 브리지 노드 자동 탐지

---

## 개발 이력

| 날짜 | 마일스톤 |
|------|---------|
| 2026-06-20 | P0: 9개 프로젝트 폴더 구조, Wiki 기본 구성, CLAUDE.md 작성 |
| 2026-06-20 | P1: ingest.py Ollama 연동, build_home.py 최근변경/이슈 탭 추가 |
| 2026-06-20 | P2: build_graph.py D3.js 지식 그래프, graphify_run.py 9개 프로젝트 AST |
| 2026-06-20 | P3: watch_wiki.py watchdog 데몬, start.bat 원클릭 자동화 |
| 2026-06-20 | QA: Obsidian Dataview+Templater 설치, 전체 파이프라인 검증 완료 |

---

## 실행 방법

```bat
# 원클릭 전체 갱신 (루트에서)
start.bat

# Cowork에서 말로
"위키 업데이트해줘"   → python scripts/ingest.py && build_graph.py && build_home.py
"전체 갱신해줘"       → python scripts/graphify_run.py && ingest.py && build_graph.py && build_home.py
"AST 분석해줘"        → python scripts/graphify_run.py
```

---

## 미해결 과제 (백로그)

- [ ] 산출물 워크플로우: 위키 지식 → 보고서·문서 자동 생성
- [ ] Obsidian Graph View와 build_graph.py 연동 심화
- [ ] 프로젝트별 Wiki 심화 (Graphify AST 결과 → Concepts/Entities 반영)
