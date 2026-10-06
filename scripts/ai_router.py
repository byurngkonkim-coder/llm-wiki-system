#!/usr/bin/env python3
"""
ai_router.py — LLM Wiki 하이브리드 AI 라우터
=============================================
1순위: Ollama (로컬, 토큰 무료, 완전 프라이버시)
2순위: Claude API (클라우드 폴백, 고품질)

사용 방법:
    from ai_router import ask_ai

    # 기본 사용 (Ollama 우선 → Claude 폴백 자동)
    answer = ask_ai("이 코드를 요약해줘", context="...")

    # 특정 엔진 지정
    answer = ask_ai("...", engine="ollama")   # 로컬만
    answer = ask_ai("...", engine="claude")   # 클라우드만

CLI:
    python ai_router.py --test
    python ai_router.py "질문"
    python ai_router.py "질문" --engine ollama
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── 설정 로드 ────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent.parent / "ai_config.json"

def _load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    # 기본값 (setup_ollama.bat 실행 전)
    return {
        "routing": {"primary": "ollama", "fallback": "claude"},
        "ollama": {
            "base_url": "http://localhost:11434",
            "default_model": "gemma3:4b",
            "timeout_seconds": 60
        },
        "claude": {
            "default_model": "claude-haiku-4-5-20251001",
            "api_key_env": "ANTHROPIC_API_KEY"
        }
    }

CONFIG = _load_config()


# ── Ollama 연결 확인 ─────────────────────────────────────────────────────────

def is_ollama_running() -> bool:
    """Ollama 서버가 실행 중인지 확인 (타임아웃 2초)"""
    try:
        base = CONFIG["ollama"]["base_url"]
        req = urllib.request.urlopen(f"{base}/api/tags", timeout=2)
        return req.status == 200
    except Exception:
        return False


def get_ollama_models() -> list[str]:
    """설치된 Ollama 모델 목록"""
    try:
        base = CONFIG["ollama"]["base_url"]
        req = urllib.request.urlopen(f"{base}/api/tags", timeout=3)
        data = json.loads(req.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ── Ollama 호출 ──────────────────────────────────────────────────────────────

def ask_ollama(
    prompt: str,
    system: str = "",
    model: str = None,
    temperature: float = 0.3
) -> str:
    """
    Ollama 로컬 LLM 호출 (OpenAI-compatible Chat API 사용)

    Returns:
        응답 텍스트 (실패 시 빈 문자열)
    """
    model = model or CONFIG["ollama"]["default_model"]
    base  = CONFIG["ollama"]["base_url"]
    timeout = CONFIG["ollama"].get("timeout_seconds", 60)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature}
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{base}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise ConnectionError(f"Ollama 연결 실패: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"Ollama 호출 오류: {e}") from e


# ── Claude API 호출 ───────────────────────────────────────────────────────────

def ask_claude(
    prompt: str,
    system: str = "",
    model: str = None,
    max_tokens: int = 2048
) -> str:
    """
    Claude API 직접 호출 (SDK 없이 urllib 사용 — pkg 번들 호환)

    Returns:
        응답 텍스트 (실패 시 예외 발생)
    """
    model = model or CONFIG["claude"]["default_model"]
    api_key_env = CONFIG["claude"].get("api_key_env", "ANTHROPIC_API_KEY")
    api_key = os.environ.get(api_key_env, "")

    if not api_key:
        raise RuntimeError(
            f"Claude API 키 없음. 환경변수 {api_key_env} 를 설정하거나\n"
            "Raw 폴더의 API 키 파일을 확인하세요."
        )

    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system or "당신은 유능한 AI 어시스턴트입니다.",
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Claude API 오류 {e.code}: {body}") from e


# ── 메인 라우터 ──────────────────────────────────────────────────────────────

def ask_ai(
    prompt: str,
    system: str = "",
    engine: str = "auto",
    task_type: str = None,
    verbose: bool = True
) -> str:
    """
    하이브리드 AI 라우터 — Ollama 우선, Claude 폴백

    Args:
        prompt:    질문/요청 텍스트
        system:    시스템 프롬프트 (선택)
        engine:    "auto" | "ollama" | "claude"
        task_type: "text_correction" | "summarization" | "code_analysis" | ...
                   (ai_config.json 의 task_model_map 참조)
        verbose:   라우팅 상태 출력 여부

    Returns:
        AI 응답 텍스트
    """

    # task_type으로 엔진 결정
    if engine == "auto" and task_type:
        task_map = CONFIG.get("task_model_map", {})
        engine = task_map.get(task_type, "auto")

    routing = CONFIG.get("routing", {})
    primary  = routing.get("primary", "ollama")
    fallback = routing.get("fallback", "claude")

    def _log(msg: str):
        if verbose:
            print(msg, flush=True)

    # ── 명시적 엔진 지정 ──
    if engine == "ollama":
        _log("[Ollama] 로컬 LLM 호출 중...")
        return ask_ollama(prompt, system)

    if engine == "claude":
        _log("[Claude] API 호출 중...")
        return ask_claude(prompt, system)

    # ── auto: 1순위 → 폴백 ──
    if primary == "ollama":
        if not is_ollama_running():
            _log("[Ollama] 서버 미실행 → Claude로 전환")
        else:
            try:
                _log("[Ollama] 로컬 LLM 호출 중...")
                t0 = time.time()
                result = ask_ollama(prompt, system)
                _log(f"[Ollama] 완료 ({time.time()-t0:.1f}초)")
                return result
            except Exception as e:
                _log(f"[Ollama] 실패: {e} → Claude로 전환")

    # 폴백
    _log(f"[Claude] {CONFIG['claude']['default_model']} 호출 중...")
    t0 = time.time()
    result = ask_claude(prompt, system)
    _log(f"[Claude] 완료 ({time.time()-t0:.1f}초)")
    return result


# ── 태스크별 래퍼 함수 ────────────────────────────────────────────────────────

def correct_text(text: str, rules: str = "") -> str:
    """텍스트 교정 (Ollama 우선)"""
    system = "당신은 한국어 텍스트 교정 전문가입니다. 원본 의미를 유지하면서 정확하게 교정하세요."
    prompt = f"다음 텍스트를 교정해주세요:\n\n{text}"
    if rules:
        prompt += f"\n\n적용 규칙:\n{rules}"
    return ask_ai(prompt, system, task_type="text_correction")


def summarize(text: str, max_length: int = 200) -> str:
    """텍스트 요약 (Ollama 우선)"""
    system = "당신은 핵심만 추출하는 요약 전문가입니다."
    prompt = f"다음 내용을 {max_length}자 이내로 핵심만 요약하세요:\n\n{text}"
    return ask_ai(prompt, system, task_type="summarization")


def analyze_code(code: str, question: str = "") -> str:
    """코드 분석 (Claude 우선)"""
    system = "당신은 시니어 소프트웨어 엔지니어입니다."
    prompt = f"다음 코드를 분석해주세요:\n\n```\n{code}\n```"
    if question:
        prompt += f"\n\n질문: {question}"
    return ask_ai(prompt, system, engine="claude", task_type="code_analysis")


def generate_wiki_content(topic: str, source_info: str = "") -> str:
    """위키 문서 내용 생성 (Ollama 우선)"""
    system = (
        "당신은 기술 문서 작성 전문가입니다. "
        "Obsidian 마크다운 형식으로 작성하고, "
        "[[링크]] 형태의 위키링크를 적극 사용하세요."
    )
    prompt = f"'{topic}' 에 대한 위키 문서를 작성해주세요."
    if source_info:
        prompt += f"\n\n참고 정보:\n{source_info}"
    return ask_ai(prompt, system, task_type="wiki_generation")


# ── 상태 확인 ─────────────────────────────────────────────────────────────────

def status() -> dict:
    """현재 AI 라우터 상태 반환"""
    ollama_ok = is_ollama_running()
    ollama_models = get_ollama_models() if ollama_ok else []
    api_key = os.environ.get(CONFIG["claude"].get("api_key_env", "ANTHROPIC_API_KEY"), "")

    return {
        "ollama": {
            "running": ollama_ok,
            "models": ollama_models,
            "default": CONFIG["ollama"]["default_model"]
        },
        "claude": {
            "api_key_set": bool(api_key),
            "default_model": CONFIG["claude"]["default_model"]
        },
        "routing": CONFIG.get("routing", {})
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_status():
    s = status()
    print("\n=== AI 라우터 상태 ===")
    print(f"1순위 Ollama: {'✅ 실행 중' if s['ollama']['running'] else '❌ 미실행'}")
    if s["ollama"]["models"]:
        print(f"  설치 모델: {', '.join(s['ollama']['models'])}")
    print(f"  기본 모델: {s['ollama']['default']}")
    print(f"\n2순위 Claude: {'✅ API 키 있음' if s['claude']['api_key_set'] else '⚠️  API 키 없음'}")
    print(f"  기본 모델: {s['claude']['default_model']}")
    print(f"\n라우팅 순서: {s['routing'].get('primary','ollama')} → {s['routing'].get('fallback','claude')}")


def _run_test():
    print("\n=== AI 라우터 동작 테스트 ===")
    _print_status()

    test_prompt = "1+1은 얼마인가요? 한 문장으로만 답하세요."

    print("\n[테스트] 'Ollama' 연결 테스트...")
    if is_ollama_running():
        try:
            result = ask_ollama(test_prompt)
            print(f"  Ollama 응답: {result[:100]}")
        except Exception as e:
            print(f"  Ollama 오류: {e}")
    else:
        print("  Ollama 미실행 — setup_ollama.bat 실행 후 재시도")

    print("\n[테스트] '자동 라우터' 테스트...")
    try:
        result = ask_ai(test_prompt, verbose=True)
        print(f"  최종 응답: {result[:100]}")
        print("\n✅ 라우터 정상 동작!")
    except Exception as e:
        print(f"\n❌ 오류: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI 라우터 — Ollama 우선, Claude 폴백")
    parser.add_argument("prompt", nargs="?", help="질의할 내용")
    parser.add_argument("--engine", choices=["auto", "ollama", "claude"], default="auto")
    parser.add_argument("--system", default="", help="시스템 프롬프트")
    parser.add_argument("--test", action="store_true", help="동작 테스트")
    parser.add_argument("--status", action="store_true", help="상태 확인")
    args = parser.parse_args()

    if args.test:
        _run_test()
    elif args.status:
        _print_status()
    elif args.prompt:
        result = ask_ai(args.prompt, system=args.system, engine=args.engine)
        print(f"\n응답:\n{result}")
    else:
        parser.print_help()
