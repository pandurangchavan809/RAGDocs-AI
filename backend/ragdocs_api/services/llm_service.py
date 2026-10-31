import os
import re
import time
from functools import lru_cache

from openai import OpenAI

from .gemini_service import (
    get_gemini_api_key,
    get_gemini_client,
    get_gemini_config,
    get_gemini_generation_config,
)

AUTO_MODEL = "auto"
REQUEST_TIMEOUT_SECONDS = 45

DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_NEBIUS_MODELS = (
    "nvidia/Nemotron-3_5-Lightning,Qwen/Qwen3-235B-A22B-Instruct-2507"
)
DEFAULT_OPENAI_MODELS = "gpt-4.1"

WORD_PIECE = re.compile(r"\s*\S+\s*")
GEMINI_WORD_DELAY_SECONDS = 0.012


def get_env_list(name, default):
    raw_value = os.getenv(name, "").strip() or default
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def get_provider_api_key(provider):
    if provider == "gemini":
        return get_gemini_api_key()
    if provider == "nebius":
        return os.getenv("NEBIUS_API_KEY", "").strip()
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY", "").strip()
    return ""


def get_declared_models():
    """Every model we know about, in display order, with or without an API key."""
    declared = [
        ("nebius", "Nebius Token Factory", name)
        for name in get_env_list("NEBIUS_MODELS", DEFAULT_NEBIUS_MODELS)
    ]
    declared.append(("gemini", "Google Gemini", get_gemini_config()["model"]))
    declared.extend(
        ("openai", "OpenAI", name)
        for name in get_env_list("OPENAI_MODELS", DEFAULT_OPENAI_MODELS)
    )
    return declared


def get_role_ids():
    declared = get_declared_models()
    primary = os.getenv("LLM_PRIMARY_MODEL", "").strip() or (
        f"{declared[0][0]}:{declared[0][2]}"
    )
    secondary = os.getenv("LLM_SECONDARY_MODEL", "").strip() or (
        f"gemini:{get_gemini_config()['model']}"
    )
    return primary, secondary


def get_available_models():
    """Only models the backend can really call, shaped for the model picker."""
    primary, secondary = get_role_ids()
    models = []

    for provider, provider_label, name in get_declared_models():
        if not get_provider_api_key(provider):
            continue

        model_id = f"{provider}:{name}"
        roles = []
        if model_id == primary:
            roles.append("primary")
        if model_id == secondary:
            roles.append("secondary")

        models.append(
            {
                "id": model_id,
                "label": name.rsplit("/", 1)[-1],
                "name": name,
                "provider": provider,
                "provider_label": provider_label,
                "roles": roles,
            }
        )

    return models


def get_auto_chain():
    available_ids = [model["id"] for model in get_available_models()]
    chain = [model_id for model_id in get_role_ids() if model_id in available_ids]
    return list(dict.fromkeys(chain)) or available_ids[:1]


def is_selectable_model(model_id):
    if model_id == AUTO_MODEL:
        return True
    return any(model["id"] == model_id for model in get_available_models())


@lru_cache(maxsize=4)
def get_openai_compatible_client(api_key, base_url):
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )


def get_model_label(model_id):
    return model_id.split(":", 1)[-1].rsplit("/", 1)[-1]


def stream_with_gemini(model_name, prompt):
    stream = get_gemini_client().models.generate_content_stream(
        model=model_name,
        contents=prompt,
        config=get_gemini_generation_config(),
    )
    # Gemini sends large blocks, so release each one word by word like the other models.
    for chunk in stream:
        for word in WORD_PIECE.findall(chunk.text or ""):
            yield word
            time.sleep(GEMINI_WORD_DELAY_SECONDS)


def stream_with_openai_compatible(provider, model_name, prompt):
    settings = get_gemini_config()
    params = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings["temperature"],
        "stream": True,
    }

    if provider == "nebius":
        base_url = os.getenv("NEBIUS_BASE_URL", "").strip() or DEFAULT_NEBIUS_BASE_URL
        params["max_tokens"] = settings["max_output_tokens"]
        params["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    else:
        base_url = None
        params["max_completion_tokens"] = settings["max_output_tokens"]

    client = get_openai_compatible_client(get_provider_api_key(provider), base_url)
    for chunk in client.chat.completions.create(**params):
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def stream_with_model(model_id, prompt):
    provider, model_name = model_id.split(":", 1)
    if provider == "gemini":
        return stream_with_gemini(model_name, prompt)
    return stream_with_openai_compatible(provider, model_name, prompt)


def stream_answer(prompt, model_id=AUTO_MODEL):
    """Yield model and token events. Auto falls back only before the first token,
    since text already sent to the user can't be taken back."""
    chain = get_auto_chain() if model_id == AUTO_MODEL else [model_id]
    if not chain:
        raise ValueError(
            "No AI model is configured. Add an API key to backend/.env and restart."
        )

    last_error = None
    for candidate in chain:
        yield {"type": "model_start", "model": candidate}
        started = False
        try:
            for text in stream_with_model(candidate, prompt):
                started = True
                yield {"type": "token", "text": text}
            if started:
                return
            last_error = ValueError(
                f"{get_model_label(candidate)} returned an empty response."
            )
        except Exception as exc:
            if started:
                raise
            last_error = exc
        yield {"type": "model_failed", "model": candidate}

    raise last_error
