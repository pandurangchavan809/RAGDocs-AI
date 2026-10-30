import os
import re
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

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


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


def generate_with_gemini(model_name, prompt):
    response = get_gemini_client().models.generate_content(
        model=model_name,
        contents=prompt,
        config=get_gemini_generation_config(),
    )
    return response.text or ""


def generate_with_openai_compatible(provider, model_name, prompt):
    settings = get_gemini_config()
    params = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings["temperature"],
    }

    if provider == "nebius":
        base_url = os.getenv("NEBIUS_BASE_URL", "").strip() or DEFAULT_NEBIUS_BASE_URL
        params["max_tokens"] = settings["max_output_tokens"]
    else:
        base_url = None
        params["max_completion_tokens"] = settings["max_output_tokens"]

    client = get_openai_compatible_client(get_provider_api_key(provider), base_url)
    response = client.chat.completions.create(**params)
    return THINK_BLOCK.sub("", response.choices[0].message.content or "")


def generate_with_model(model_id, prompt):
    provider, model_name = model_id.split(":", 1)
    if provider == "gemini":
        text = generate_with_gemini(model_name, prompt)
    else:
        text = generate_with_openai_compatible(provider, model_name, prompt)

    text = text.strip()
    if not text:
        raise ValueError(f"{model_name} returned an empty response.")
    return text


def generate_answer(prompt, model_id=AUTO_MODEL):
    """Auto tries primary then secondary. A model the user picked gets no fallback."""
    chain = get_auto_chain() if model_id == AUTO_MODEL else [model_id]
    if not chain:
        raise ValueError(
            "No AI model is configured. Add an API key to backend/.env and restart."
        )

    last_error = None
    for candidate in chain:
        try:
            return {"text": generate_with_model(candidate, prompt), "model": candidate}
        except Exception as exc:
            last_error = exc

    raise last_error
