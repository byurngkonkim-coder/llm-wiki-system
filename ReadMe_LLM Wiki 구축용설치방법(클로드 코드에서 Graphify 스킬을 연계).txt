LLM Wiki 구축용(클로드 코드(Claude Code)에서 Graphify 스킬을 연계 설치방법)

3가지 방법을 제안합니다. 가장 실용적인 방법부터 설명하겠습니다.정상 작동합니다. 파일을 공유합니다.3가지 적용 방법을 정리합니다.

---

## 방법 1 — `wiki_setup.bat` 더블클릭 (가장 간단)

`D:\백업\utility\` 에 저장된 두 파일을 새 폴더 근처에 복사하거나, 탐색기에서 **`wiki_setup.bat`를 더블클릭**하면 됩니다.

```
실행 후 순서:
① 폴더 경로 입력  →  D:\새프로젝트\기획자료
② 프로젝트 이름 입력  →  엔터 (폴더명 자동 사용)
③ 한 줄 설명 입력  →  엔터 (생략 가능)
④ wiki 폴더명  →  엔터 (wiki 기본값)
```

10초 안에 완료.

---

## 방법 2 — 명령 프롬프트에서 경로 인자 전달

```cmd
python D:\백업\utility\wiki_setup.py "D:\새폴더\프로젝트명"
```

---

## 방법 3 — Cowork에서 "설치해줘" 요청

새 폴더를 Cowork에 연결한 뒤 **"이 폴더에 LLM Wiki 세팅해줘"** 라고 말하면, 저는 `wiki_setup.py` 스크립트를 실행해 동일하게 적용합니다.

---

**설치 후 생성되는 파일 구조:**

```
새폴더/
├── CLAUDE.md            ← AI 운영 규칙 (원본보호+LLM Wiki+3대워크플로우)
├── raw/                 ← 원본 파일을 여기에 넣기
├── wiki/
│   ├── index.md         ← 마스터 인덱스
│   └── 용어집.md
├── graphify-out/
│   └── GRAPH_REPORT.md
├── wiki_산출물/
└── .claude/
    └── settings.json    ← PreToolUse 훅 (raw/ 검색 전 그래프 먼저 확인)
```