# 🤖 나만의 세컨드 브레인: LLM Wiki 및 Graphify 운영 지침

> **이 파일은 Claude Code가 프로젝트 진입 시 자동으로 읽는 컨트롤 타워입니다.**
> Graphify AST 분석 + Karpathy LLM Wiki 사상을 결합하여 지식이 복리로 성장하는 시스템을 운영합니다.

---

## 1. 시스템 개요 및 목적 (Purpose)

- 이 프로젝트는 사용자의 업무 노하우, 개발 프로젝트 지식, 리서치 데이터를 복리로 축적하는 **나만의 LLM Wiki** 시스템이다.
- 목적: 단순 RAG의 단기 기억 상실(Amnesia)을 극복하고, 지식을 미리 컴파일하여 **영구적인 지식 저장소**로 구조화한다.
- 핵심 원칙: 할루시네이션 차단 (원본 소스 기반만), 토큰 절감 (Graphify 전처리 + Ollama 로컬), 지식 복리 성장 (링크 연결)

### AI 엔진 우선순위

| 순위 | 엔진 | 용도 | 비용 |
|------|------|------|------|
| 1순위 | Ollama (로컬) | 텍스트 교정·요약·위키 생성 | 무료 |
| 2순위 | Claude API | 복잡한 추론·코드 분석·폴백 | 유료 |

**라우팅 모듈**: `ai_router.py` — `from ai_router import ask_ai` 로 임포트해 사용.
**설정 파일**: `ai_config.json` — 모델명, 타임아웃, 태스크별 엔진 지정.
**모델 기본값**: Ollama=`gemma3:4b`, Claude=`claude-haiku-4-5-20251001`

### 사용자 프로필

| 항목 | 내용 |
|------|------|
| 역할 | 기획자 / PM (비개발자) |
| 주요 도메인 | AI/LLM 활용, 개발 프로젝트 관리, 업무 자동화, 지식 관리 / Second Brain |
| 관리 프로젝트 수 | 9개 개발 프로젝트 |
| Wiki 도구 | Obsidian (로컬 Vault) + Claude Code + Graphify |

---

## 2. 폴더 구조 및 역할 정의 (Architecture)

> 모든 폴더는 **플랫(Flat)** 구조로 유지하여 에이전트의 탐색 토큰 낭비를 예방한다.

```
개발프로그램/              ← Obsidian Vault 루트
│
├── CLAUDE.md              ← 현재 파일 (컨트롤 타워, Claude Code 자동 읽기)
│
├── Raw/                   ← 원본 소스 (읽기 전용, 수정/삭제 절대 금지)
│   ├── MBO_업무일지관리시스템/
│   │   ├── [소스코드]
│   │   ├── Wiki/          ← 프로젝트별 세부 위키
│   │   └── Schema/CLAUDE.md  ← 프로젝트별 AI 지침
│   └── ... (9개 프로젝트 동일 구조)
│
├── Wiki/                  ← AI가 정제·생성하는 통합 지식 마크다운 보관소
│   ├── index.md           ← 전체 지식의 유기적 목차 (카테고리 허브)
│   ├── log.md             ← 지식 편집/추가 이력 타임라인 로그
│   ├── hot.md             ← 현재 진행 중인 핵심 프로젝트 & 최근 작업 메모리 일지
│   ├── Summaries/         ← 프로젝트별 요약 (자동 생성)
│   ├── Concepts/          ← 핵심 개념 정의
│   ├── Entities/          ← 기술·라이브러리·도구 등
│   ├── Topics/            ← 주제별 통합 정리
│   └── GraphData/         ← Graphify 출력 (graph.json, graph.html)
│
└── Schema/                ← 전체 운영 규칙 문서
    └── CLAUDE.md          ← 상세 포맷 규칙 (이 파일보다 상세)
```

---

## 3. 3대 핵심 운영 프로세스

### ① 수집 및 소화 (Ingest / Write-Time Compilation)

새로운 문서(PDF, 웹 클리핑, 메모, 코드)가 `Raw/` 폴더에 추가되면:

1. **절대 원본 파일을 처음부터 전체 읽지 않는다** — 토큰 낭비 차단
2. **반드시 먼저 Graphify 스킬 실행** → AST 기반 기계적 구조 분석 → 지식 뼈대 추출
   ```
   /graphify Raw/프로젝트명
   ```
3. 도출된 지식 관계망 기반으로 `Wiki/` 폴더에 마크다운 생성 또는 기존 노트 **병합(Merge) 업데이트**
4. `Wiki/index.md` 목차 및 `Wiki/log.md` 작업 로그 최신화
5. 관련 개념은 `[[개념명]]` 링크로 반드시 연결

**자동화 명령:**
```bash
python scripts/ingest.py              # 전체 Summary 업데이트
python scripts/build_graph.py         # 지식 그래프 재생성
# 또는 (PC에서):
run_graphify.bat 프로젝트명            # AST 추출 (토큰 0) → Wiki/GraphData/{프로젝트}/
```

### ② 질문 및 탐색 (Query)

사용자가 지식에 대해 질문할 때:

1. `Raw/` 전체를 매번 재검색하지 않는다
2. **반드시 `Wiki/index.md` 또는 `Wiki/GraphData/graph.json` 먼저 확인**
3. 맥락적으로 가장 연관성 높은 위키 페이지 **5~7개만 선택적으로** 열어 참조
4. 훌륭한 답변이나 새 인사이트는 사용자 요청 시 `Wiki/` 페이지로 재기록 → 지식 복리 축적

**컨텍스트 주입 순서:**
```
Wiki/hot.md → Wiki/index.md → Wiki/GraphData/{프로젝트}/GRAPH_REPORT.md → 관련 Concepts/ → 관련 Summaries/ → 필요 시 Raw/
```

**Graphify 컨텍스트 로드 (토큰 절감):**
```bash
# 특정 프로젝트의 코드 구조 요약 (토큰 없음)
python graphify_context.py MBO_업무일지관리시스템

# 특정 개념 검색
python graphify_context.py --query "SQLite"

# 사용 가능한 그래프 목록
python graphify_context.py --list
```

### ③ 건강검진 (Lint)

정기 또는 요청 시 위키 무결성 검사:

| 검사 항목 | 설명 |
|-----------|------|
| 고립 페이지 (Orphan) | 다른 위키와 연결 고리가 없는 문서 |
| 깨진 링크 | `[[링크]]` 대상 파일 미존재 |
| 빠진 개념 정의 | 본문에서 참조하나 Concepts/ 파일 없음 |
| 충돌 내용 | 여러 소스 간 상충하는 정보 |

검사 결과를 리포트로 제출 후 **승인 하에만** 교정 실행.

```bash
python scripts/ingest.py --lint
```

---

## 4. 문서 작성 엄격 규칙

### ✅ Takeaway 최우선 법칙
모든 위키 문서 맨 위에 `> [!NOTE]` 블록으로 **실행 가능한 핵심 Takeaway 3줄 이내** 작성.

```markdown
> [!NOTE]
> **핵심 Takeaway**
> 1. (실행 가능한 인사이트 1)
> 2. (실행 가능한 인사이트 2)
> 3. (실행 가능한 인사이트 3)
```

### ✅ 교차 참조 활성화
중요한 개념·도구·인물 등장 시 반드시 `[[개념명]]` Obsidian 위키링크 생성.

### ✅ 출처 표기 의무화
모든 정보에 원본 파일 역추적 가능하도록 메타데이터 명시:
```markdown
---
source: Raw/프로젝트명/파일경로
created: YYYY-MM-DD
---
```

### ❌ 덮어쓰기 금지
기존 위키 수정 시 이전 내용과 사용자 메모를 **병합(Merge)** 방식으로만 처리.

### ✅ 신뢰도 구분 표기

| 태그 | 의미 |
|------|------|
| `[EXTRACTED]` | 원본 소스에서 직접 추출된 사실 |
| `[INFERRED]` | AI가 맥락으로 추론한 내용 |
| `[AMBIGUOUS]` | 불확실하거나 검증 필요한 내용 |
| `[미확인]` | 추가 확인이 필요한 정보 |
| `[상충]` | 소스 간 의견 충돌 발생 |

---

## 5. Graphify 연계 운영 지침

Graphify는 **AI 없이 AST(추상 구문 트리)로 코드 구조를 파악**하여 토큰을 아끼는 전처리 도구다.

### 설치 (PC에서 1회만 실행)
```bat
setup_graphify.bat        ← 더블클릭 → pip install graphifyy 자동 실행
```

### 코드 구조 추출 (토큰 없음)
```bat
# PC에서 실행 (배치 파일)
run_graphify.bat MBO_업무일지관리시스템    ← 특정 프로젝트 AST 추출
run_graphify.bat                           ← 전체 Raw 폴더

# Claude Code / Cowork 스킬 실행
/graphify Raw/MBO_업무일지관리시스템
/graphify path "SQLite" "Express API"
/graphify explain "MBO시스템"
```

### 에이전트에 컨텍스트 전달
```bash
python graphify_context.py MBO_업무일지관리시스템   # 코드 구조 요약 출력
python graphify_context.py --query "SQLite"         # 특정 개념 검색
python graphify_context.py --list                   # 그래프 목록
```

### 처리 흐름 (토큰 절감 구조)
```
코드파일 (.py/.ts/.js) → AST 추출 → graph.json    ← 토큰 0원
문서파일 (.md/.txt)    → 메타데이터만             ← 토큰 0원
이미지/PDF             → Claude Vision 분석        ← 토큰 사용
```

### Graphify 출력 결과 저장 위치
```
Wiki/GraphData/{프로젝트명}/
├── graph.json       — 지속적 지식 그래프 (세션 간 유지)
├── GRAPH_REPORT.md  — 허브 노드, 놀라운 연결, 제안 질문
└── graph.html       — 브라우저 인터랙티브 시각화
```

---

## 6. Cowork 명령어 레퍼런스 (말로 요청하는 방법)

> Claude는 아래 명령을 받으면 bash 도구로 해당 Python 스크립트를 직접 실행한다.
> 스크립트 경로 기준: `/sessions/loving-keen-hawking/mnt/개발프로그램/`

### 🔄 Wiki 갱신 명령

| 사용자 말 | Claude 실행 내용 | 소요 시간 |
|-----------|-----------------|-----------|
| `"위키 업데이트해줘"` | `python ingest.py && python build_graph.py && python build_home.py` | ~1분 |
| `"전체 갱신해줘"` / `"full refresh"` | `python graphify_run.py && python ingest.py && python build_graph.py && python build_home.py` | ~2분 |
| `"그래프만 새로고침해줘"` | `python build_graph.py && python build_home.py` | ~5초 |
| `"AST 분석해줘"` | `python graphify_run.py` | ~20초 |

### 📖 조회 명령

| 사용자 말 | Claude 동작 |
|-----------|------------|
| `"MBO 프로젝트 정리해줘"` | `Wiki/GraphData/MBO_.../GRAPH_REPORT.md` + 관련 위키 5~7개 참조 |
| `"위키 린트해줘"` | Orphan·깨진링크·충돌 점검 → 리포트 |
| `"오늘 작업 메모해줘"` | `Wiki/hot.md` 업데이트 |
| `"이번 주 진행상황 정리해줘"` | `hot.md` + `log.md` 기반 요약 |
| `"SQLite 관련 코드 구조 알려줘"` | `python graphify_context.py --query "SQLite"` 실행 |

### 💻 수동 실행 (Windows에서 직접)

| 파일 | 용도 |
|------|------|
| `start.bat` | 전체 갱신 + 브라우저 열기 (더블클릭) |
| `wiki_refresh.bat` | 빠른 갱신 (Graphify 제외) |
| `run_graphify.bat` | AST 분석만 |
