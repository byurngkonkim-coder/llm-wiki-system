# LLM Wiki 시스템 — 나만의 세컨드 브레인

> [!NOTE]
> **핵심 Takeaway**
> 1. `start.bat` 더블클릭 한 번으로 9개 프로젝트 AST 분석 + AI 요약 + 대시보드 생성이 완료된다.
> 2. AI 엔진은 Ollama(로컬, 무료) 우선 → 실패 시 Claude API 자동 폴백.
> 3. Graphify AST로 코드 구조를 토큰 0원에 추출하여 할루시네이션을 차단한다.

---

## 시스템 개요

Karpathy의 LLM 코딩 사상 + Graphify AST 분석을 결합하여,
9개 개발 프로젝트의 소스코드와 문서를 자동으로 분석·요약하는 **영구 지식 저장소**입니다.

```
Raw/ (원본 소스)
  └── 9개 프로젝트
        ↓ graphify_run.py (AST, 토큰 0원)
        ↓ ingest.py (Ollama gemma2:2b 요약)
Wiki/ (지식 저장소)
  ├── Summaries/     ← 프로젝트 요약 9개
  ├── Concepts/      ← 핵심 개념 9개
  ├── Entities/      ← 기술·라이브러리 8개
  ├── Topics/        ← 주제별 정리 7개
  ├── GraphData/     ← AST 그래프 9개 + 지식 그래프
  └── home.html      ← 통합 대시보드 (브라우저에서 열기)
```

## 빠른 시작

```bat
start.bat   ← 더블클릭으로 전체 실행
```

## 처리 파이프라인

| 단계 | 스크립트 | 소요 시간 | 토큰 |
|------|---------|----------|------|
| AST 코드 분석 | graphify_run.py | ~11초 | 0원 |
| AI 프로젝트 요약 | ingest.py | ~3분 | Ollama 무료 |
| 지식 그래프 생성 | build_graph.py | ~1초 | 0원 |
| 대시보드 생성 | build_home.py | ~1초 | 0원 |

## QA 결과 (2026-06-20)

- ✅ 9개 프로젝트 AST 분석 — 전체 성공, 오류 0건
- ✅ Ollama gemma2:2b 요약 생성 — 9개 완료
- ✅ 지식 그래프 — 노드 33개, 엣지 73개
- ✅ home.html — 프로젝트 9 / 최근변경 46 / 미해결이슈 6
- ✅ Obsidian Dataview + Templater 플러그인 설치 완료
