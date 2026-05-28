import os
from functools import lru_cache

from google import genai
from google.genai import types


def get_env_float(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def get_env_int(name, default):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


@lru_cache(maxsize=1)
def get_gemini_config():
    return {
        "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        "temperature": get_env_float("GEMINI_TEMPERATURE", 0.1),
        "max_output_tokens": get_env_int("GEMINI_MAX_OUTPUT_TOKENS", 1536),
        "thinking_budget": get_env_int("GEMINI_THINKING_BUDGET", 256),
    }


def get_gemini_api_key():
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


@lru_cache(maxsize=1)
def get_gemini_client():
    api_key = get_gemini_api_key()
    if not api_key:
        raise ValueError(
            "Set GEMINI_API_KEY or GOOGLE_API_KEY in backend/.env before using chat."
        )
    return genai.Client(api_key=api_key)


def get_gemini_generation_config():
    config = get_gemini_config()
    return types.GenerateContentConfig(
        temperature=config["temperature"],
        max_output_tokens=config["max_output_tokens"],
        thinking_config=types.ThinkingConfig(
            thinking_budget=config["thinking_budget"]
        ),
        response_mime_type="text/plain",
    )
