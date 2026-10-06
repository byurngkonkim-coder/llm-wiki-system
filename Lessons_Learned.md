# LLM Wiki 시스템 — Lessons Learned

> [!NOTE]
> **핵심 Takeaway**
> 1. Windows bat 파일은 처음부터 Python으로 ASCII+CRLF 작성한다 (한글·이모지 절대 금지).
> 2. 모든 Python 스크립트는 처음부터 `Path(__file__).parent.parent`로 루트 참조한다.
> 3. 외부 라이브러리 반환 타입은 가정하지 말고 `isinstance()` 방어 코드를 넣는다.

---

## 1. 잘된 점 (Achievements)

### ✅ 핵심 파이프라인 완성
| 항목 | 성과 |
|------|------|
| Graphify AST 분석 | 9개 프로젝트, 토큰 0원, 11초 완료 |
| Ollama 연동 | gemma2:2b 로컬 실행, 비용 0원 |
| 원클릭 자동화 | `start.bat` 하나로 전체 파이프라인 실행 |
| 지식 그래프 | D3.js 인터랙티브, 노드 33개·엣지 73개 |
| 대시보드 | home.html 6개 탭, 서버 없이 브라우저에서 즉시 열기 |
| Obsidian 연동 | Dataview + Templater 플러그인 설치·활성화 |
| 폴더 정리 | scripts/ 분리로 루트 파일 3개로 정돈 |

### ✅ 설계 결정이 옳았던 것들
- **Ollama 우선 + Claude 폴백**: 인터넷 없이도 동작, 비용 절감
- **`BASE = Path(__file__).parent`**: 스크립트 이동 후 경로 수정이 `.parent` 하나 추가로 해결됨
- **플랫(Flat) 폴더 구조**: Claude 에이전트 탐색 토큰 최소화 효과 확인
- **단일 home.html**: 서버 불필요, 더블클릭으로 즉시 확인 가능

---

## 2. 보완해야 할 점 — 오류 목록 및 조치

### 🔴 오류 1: Windows bat 파일 파싱 실패
**증상**:
```
'install' is not recognized
'tchdog' is not recognized
'◆◆!' 등 이상한 문자 출력
'h_wiki.py' is not recognized
```

**원인 (복합)**:
1. `pip install` → pip가 PATH에 없음
2. 한글·이모지(`✅`, `◆`) 포함 → CMD가 파싱 실패
3. LF 줄바꿈(Unix) → Windows CMD는 CRLF 필요
4. `chcp 65001` 사용 → 한국어 경로(`개발프로그램`)와 충돌

**조치**:
```python
# Python으로 bat 파일 생성 시 표준 패턴
lines = ["@echo off", "echo Hello"]
content = '\r\n'.join(lines) + '\r\n'
with open('file.bat', 'wb') as f:
    f.write(content.encode('ascii'))   # ASCII 강제 인코딩
```

**다음 프로젝트 적용 규칙**:
- ❌ `pip install` → ✅ `python -m pip install`
- ❌ 한글/이모지 echo → ✅ 영문만 사용
- ❌ `chcp 65001` → ✅ 제거 (한국어 경로와 충돌)
- ❌ LF 저장 → ✅ CRLF(`'\r\n'.join()` + `.encode('ascii')`)

---

### 🔴 오류 2: `unhashable type: 'dict'` (graphify_run.py)
**증상**:
```
TypeError: unhashable type: 'dict'
```
9개 프로젝트 파일은 저장됐으나 step 8 요약 출력에서 오류.

**원인**: `god_nodes(G)` 반환값이 node ID 문자열이 아닌 dict 리스트
```python
# 실제 반환값 형태
[{"id": "FileResult", "degree": 66}, ...]
# 가정했던 형태
["FileResult", ...]
```

**조치**:
```python
for g in gods[:5]:
    if isinstance(g, dict):
        node_id = (g.get("id") or g.get("node") or
                   g.get("name") or next(iter(g.values()), None))
    else:
        node_id = g
```

**교훈**: 외부 라이브러리 반환값은 타입을 가정하지 말 것. `isinstance()` 방어 코드 필수.

---

### 🔴 오류 3: f-string 백슬래시 SyntaxError
**증상**:
```
SyntaxError: f-string expression part cannot include a backslash
```

**원인**: f-string 표현식 내부에 백슬래시 포함
```python
# 잘못된 코드
print(f"{Path(src).name if src else ''}")  # .name에 내부 백슬래시 없지만
# 실제 문제 발생 패턴
f"{'\\n'.join(items)}"
```

**조치**: 표현식을 변수로 먼저 추출
```python
name = Path(src).name if src else ''
print(f"  · {name}")
```

---

### 🔴 오류 4: start.bat `\b` 이스케이프 처리
**증상**:
```
python scriptsuild_graph.py   ← \b가 백스페이스로 처리됨
python scriptsuild_home.py
```

**원인**: Python 문자열에서 `'scripts\build_graph.py'`의 `\b`가 이스케이프 시퀀스로 해석

**조치**: bat 파일 내 경로에는 백슬래시 대신 슬래시 사용
```bat
python scripts/build_graph.py   ← Windows에서도 슬래시 작동
```

---

### 🟡 오류 5: scripts/ 이동 후 BASE 경로 불일치
**증상**: 스크립트를 `scripts/`로 이동 후 `Wiki/`, `Raw/` 폴더를 찾지 못함

**원인**: `BASE = Path(__file__).parent`가 이제 `scripts/`를 가리킴

**조치**: 전체 스크립트에서 `.parent` → `.parent.parent` 수정
```python
BASE = Path(__file__).parent.parent   # scripts/ 상위 = 개발프로그램/
```

**교훈**: 처음 설계 시부터 스크립트 위치 이동을 고려해 `.parent.parent` 사용 권장.

---

### 🟡 오류 6: Ollama 앱과 서버 혼동
**증상**: `ollama serve` 실행 시 포트 충돌 오류
```
Error: listen tcp 127.0.0.1:11434: bind: Only one usage of each socket address
```

**원인**: 사용자 PC의 "Ollama" 앱이 LLM 서버가 아닌 에이전트 런처였음.
실제 `ollama serve`는 시스템 트레이에서 이미 실행 중.

**판단 기준**:
- 포트 충돌 오류 = **이미 실행 중** (정상)
- `curl http://localhost:11434` 응답 있으면 실행 중

**조치**: start.bat에 자동 감지 로직 추가
```bat
curl -s http://127.0.0.1:11434 >nul 2>&1
if errorlevel 1 (start /min "Ollama" ollama serve)
```

---

### 🟡 오류 7: graphify_context.py 변수명 공백
**증상**: `sed -i 's/BASE = .../...'` 명령이 적용 안 됨

**원인**: 변수 선언에 불규칙한 공백 포함
```python
BASE    = Path(__file__).parent   ← 공백 4개
```

**조치**: 공백 포함 패턴으로 별도 sed 명령 실행
```bash
sed -i 's/BASE    = Path(__file__).parent$/BASE    = Path(__file__).parent.parent/' file.py
```

**교훈**: 변수 선언 정렬 시 공백 대신 탭 또는 통일된 공백 1개만 사용.

---

### 🟡 오류 8: Obsidian vault picker 반복 팝업 (computer-use)
**증상**: computer-use로 Obsidian 제어 시 볼트 선택 팝업이 반복 표시되어 플러그인 브라우저 접근 어려움

**원인**: `open_application("Obsidian")` 호출 시마다 볼트 선택 다이얼로그가 앞에 표시됨

**조치**:
1. X 버튼으로 팝업 닫기 후 플러그인 브라우저 직접 클릭
2. `Ctrl+Home`으로 플러그인 상세 페이지 상단 이동

---

## 3. 다음 프로젝트 반영 체크리스트

### 설계 단계
- [ ] Python 스크립트 처음부터 `BASE = Path(__file__).parent.parent` 사용
- [ ] 변수명에 공백 정렬 사용 금지 (일반 공백 1개만)
- [ ] 외부 라이브러리 반환 타입 문서 확인 후 `isinstance()` 방어 코드 추가

### Windows bat 파일 작성
- [ ] Python으로 생성: `'\r\n'.join(lines).encode('ascii')`
- [ ] `pip install` → `python -m pip install`
- [ ] echo 라인: 영문만, 한글·이모지 금지
- [ ] `chcp 65001` 제거
- [ ] 경로 구분자: `\` 대신 `/` 사용 (이스케이프 충돌 방지)

### AI 연동
- [ ] `ai_config.json` 먼저 작성 후 `ai_router.py` 구현
- [ ] Ollama 실행 여부: `curl http://localhost:11434` 확인
- [ ] 포트 충돌 오류 = 이미 실행 중 (정상)

### 검증
- [ ] bat 파일 생성 후 `CRLF 수=라인 수`, `non-ASCII=0` 확인
- [ ] 스크립트 이동 후 `BASE` 경로 테스트 (존재하는 경로인지 확인)
- [ ] 외부 라이브러리 반환값 타입 print로 확인 후 코드 작성

---

## 4. 재사용 가능한 패턴 (Templates)

### Python 스크립트 헤더 표준
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{스크립트명} — {역할 한 줄 설명}
"""
from pathlib import Path
from ai_router import ask_ai   # AI 호출 통일 인터페이스

BASE     = Path(__file__).parent.parent   # 개발프로그램/ 루트
RAW_DIR  = BASE / "Raw"
WIKI_DIR = BASE / "Wiki"
```

### Windows bat 파일 생성 표준
```python
def write_bat(path: str, lines: list[str]):
    """ASCII + CRLF bat 파일 생성. 한글/이모지 포함 금지."""
    content = '\r\n'.join(lines) + '\r\n'
    with open(path, 'wb') as f:
        f.write(content.encode('ascii'))
    # 검증
    with open(path, 'rb') as f:
        data = f.read()
    assert data.count(b'\r\n') == len(lines), "CRLF 오류"
    assert all(b <= 127 for b in data), "non-ASCII 문자 포함"
```

### Ollama 상태 확인 + 자동 시작 (bat)
```bat
curl -s http://127.0.0.1:11434 >nul 2>&1
if errorlevel 1 (
    start /min "Ollama" ollama serve
    timeout /t 5 /nobreak >nul
)
```

### 외부 라이브러리 반환값 방어 처리
```python
def safe_extract_id(node):
    """god_nodes() 등 외부 라이브러리 반환값의 타입 방어 처리."""
    if isinstance(node, dict):
        return (node.get("id") or node.get("node") or
                node.get("name") or next(iter(node.values()), None))
    return str(node)
```

---

## 5. 프로젝트 지표

| 지표 | 수치 |
|------|------|
| 총 개발 세션 | 1일 (2026-06-20) |
| 생성된 스크립트 | 7개 Python + 8개 bat |
| 해결된 오류 건수 | 8건 |
| 최종 파이프라인 성공률 | 9/9 프로젝트 100% |
| AI 토큰 절감 (Graphify) | ~100% (AST 단계 0원) |
| 원클릭 자동화 달성 | ✅ start.bat |
