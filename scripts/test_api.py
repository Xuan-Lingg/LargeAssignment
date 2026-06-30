"""
API 连通性测试 — 在使用 Streamlit 前，先确认 LLM 能正常连接
运行: python scripts/test_api.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    GOOGLE_API_KEY, GEMINI_MODEL, GEMINI_BASE_URL,
)
from openai import OpenAI
import time


def test_deepseek():
    """测试 DeepSeek API"""
    print(f"\n[1] 测试 DeepSeek: {DEEPSEEK_MODEL}")
    print(f"    URL: {DEEPSEEK_BASE_URL}")
    print(f"    Key: {DEEPSEEK_API_KEY[:12]}...")

    client = OpenAI(base_url=DEEPSEEK_BASE_URL, api_key=DEEPSEEK_API_KEY, timeout=15)

    start = time.time()
    try:
        r = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": "回复OK"}],
            max_tokens=10,
            timeout=15,
        )
        elapsed = time.time() - start
        print(f"    [OK] 耗时 {elapsed:.1f}s → {r.choices[0].message.content}")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"    [FAIL] 耗时 {elapsed:.1f}s → {e}")
        return False


def test_gemini():
    """测试 Gemini API"""
    print(f"\n[2] 测试 Gemini: {GEMINI_MODEL}")
    print(f"    URL: {GEMINI_BASE_URL}")
    print(f"    Key: {GOOGLE_API_KEY[:12]}...")

    client = OpenAI(base_url=GEMINI_BASE_URL, api_key=GOOGLE_API_KEY, timeout=15)

    start = time.time()
    try:
        r = client.chat.completions.create(
            model=GEMINI_MODEL,
            messages=[{"role": "user", "content": "回复OK"}],
            max_tokens=10,
            timeout=15,
        )
        elapsed = time.time() - start
        print(f"    [OK] 耗时 {elapsed:.1f}s → {r.choices[0].message.content}")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"    [FAIL] 耗时 {elapsed:.1f}s → {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("  API 连通性测试")
    print("=" * 50)

    ds_ok = test_deepseek()
    gm_ok = test_gemini()

    print("\n" + "=" * 50)
    print(f"  DeepSeek: {'PASS' if ds_ok else 'FAIL'}")
    print(f"  Gemini:   {'PASS' if gm_ok else 'FAIL'}")
    print("=" * 50)

    if not ds_ok and not gm_ok:
        print("\n[!] 两个 API 都无法连接，请检查：")
        print("  1. API Key 是否正确")
        print("  2. 网络是否需要代理")
        print("  3. API Key 额度是否用完")
