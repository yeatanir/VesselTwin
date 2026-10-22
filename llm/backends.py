"""One chat interface for every provider: chat(messages) -> str, with attributes .model and .backend. Standard library only.
Providers: openai_compatible (any /v1 base URL or full /chat/completions URL), anthropic (Messages API), mlx (local), rules (offline, no chat).
Config: explicit arguments, else VT_LLM_PROVIDER / VT_LLM_BASE_URL / VT_LLM_API_KEY / VT_LLM_MODEL / VT_LLM_EXTRA_HEADERS (JSON dict).
The key lives only in the closure of the returned chat function: it is never logged, never in an exception message, never in a trace
(llm.agent logs .model and .backend only)."""
import json, os, urllib.error, urllib.request

PROVIDERS = ("openai_compatible", "anthropic", "mlx", "rules")
DEFAULT_MODEL = {"anthropic": "claude-sonnet-5-5", "mlx": "mlx-community/Qwen2.5-7B-Instruct-4bit"}


class LLMError(RuntimeError):
    """Readable provider failure; message never contains the key."""


def _post(url, headers, body, key, timeout):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read(500).decode("utf-8", "replace").replace(key, "***") if key else ""
        hint = " (check the API key)" if e.code in (401, 403) else " (check model name and base URL)" if e.code == 404 else ""
        raise LLMError(f"HTTP {e.code} from {url}{hint}: {detail}") from None
    except urllib.error.URLError as e:
        raise LLMError(f"cannot reach {url}: {e.reason}") from None
    except (ValueError, TimeoutError) as e:
        raise LLMError(f"bad or slow response from {url}: {type(e).__name__}") from None


def _headers(extra):
    if isinstance(extra, str) and extra.strip():
        try:
            extra = json.loads(extra)
        except ValueError:
            raise LLMError("extra headers must be a JSON object, e.g. {\"OpenAI-Organization\": \"org-...\"}") from None
    if not extra:
        return {}
    if not isinstance(extra, dict):
        raise LLMError("extra headers must be a JSON object")
    return {str(k): str(v) for k, v in extra.items()}


def openai_compatible_chat(base_url, model, api_key="", extra_headers=None, max_tokens=800, timeout=120):
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    hdr = {**({"authorization": "Bearer " + api_key} if api_key else {}), **_headers(extra_headers)}

    def chat(msgs):
        d = _post(url, hdr, {"model": model, "messages": msgs, "max_tokens": max_tokens}, api_key, timeout)
        try:
            return d["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("response has no choices[0].message.content") from None
    chat.model, chat.backend = model, "openai_compatible"
    return chat


def anthropic_chat(model=DEFAULT_MODEL["anthropic"], api_key="", extra_headers=None, base_url="https://api.anthropic.com", max_tokens=800, timeout=120):
    """Messages API via urllib. Extra headers (e.g. {"anthropic-workspace-id": "wrkspc_..."}) are passed through."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise LLMError("anthropic provider needs an API key (VT_LLM_API_KEY or ANTHROPIC_API_KEY)")
    hdr = {"x-api-key": api_key, "anthropic-version": "2023-06-01", **_headers(extra_headers)}
    if os.environ.get("ANTHROPIC_WORKSPACE_ID"):
        hdr.setdefault("anthropic-workspace-id", os.environ["ANTHROPIC_WORKSPACE_ID"])
    url = base_url.rstrip("/") + ("" if base_url.rstrip("/").endswith("/messages") else "/v1/messages")

    def chat(msgs):
        sys_ = "\n".join(m["content"] for m in msgs if m["role"] == "system")
        body = {"model": model, "max_tokens": max_tokens, "messages": [m for m in msgs if m["role"] != "system"]}
        if sys_:
            body["system"] = sys_
        d = _post(url, hdr, body, api_key, timeout)
        try:
            return "".join(b.get("text", "") for b in d["content"])
        except (KeyError, TypeError):
            raise LLMError("response has no content blocks") from None
    chat.model, chat.backend = model, "anthropic"
    return chat


def mlx_chat(model=DEFAULT_MODEL["mlx"], max_tokens=600):
    """Adapter over mlx_lm. Raises if mlx-lm or the model is unavailable."""
    try:
        from mlx_lm import load, generate
    except ImportError as e:
        raise LLMError("mlx provider needs `pip install mlx-lm`") from e
    m, tok = load(model)

    def chat(msgs):
        p = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        return generate(m, tok, prompt=p, max_tokens=max_tokens)
    chat.model, chat.backend = model, "mlx"
    return chat


def rules_chat():
    def chat(msgs):
        raise LLMError("the rules backend is offline and has no chat; choose a provider with --provider or VT_LLM_PROVIDER")
    chat.model, chat.backend = "none", "rules"
    return chat


def make_chat(provider=None, base_url=None, api_key=None, model=None, extra_headers=None, **kw):
    """Explicit arguments win over VT_LLM_* environment variables. Default provider: rules."""
    e = os.environ.get
    provider = (provider or e("VT_LLM_PROVIDER") or "rules").strip().lower().replace("-", "_")
    if provider == "openai":
        provider = "openai_compatible"
    base_url, api_key = base_url or e("VT_LLM_BASE_URL") or "", api_key or e("VT_LLM_API_KEY") or ""
    model, extra_headers = model or e("VT_LLM_MODEL") or DEFAULT_MODEL.get(provider, ""), extra_headers or e("VT_LLM_EXTRA_HEADERS")
    if provider == "rules":
        return rules_chat()
    if provider == "mlx":
        return mlx_chat(model, **kw)
    if provider == "anthropic":
        return anthropic_chat(model, api_key, extra_headers, **({"base_url": base_url} if base_url else {}), **kw)
    if provider == "openai_compatible":
        if not base_url or not model:
            raise LLMError("openai_compatible needs a base URL and a model name (--base-url/--model or VT_LLM_BASE_URL/VT_LLM_MODEL)")
        return openai_compatible_chat(base_url, model, api_key, extra_headers, **kw)
    raise LLMError(f"unknown provider {provider!r}; choose one of {PROVIDERS}")


def test_connection(chat):
    """One tiny request. Returns (ok, message); message never contains the key."""
    try:
        out = chat([{"role": "user", "content": "Reply with the single word: ok"}])
        return True, f"connected: {chat.backend} / {chat.model} replied {out.strip()[:40]!r}"
    except LLMError as e:
        return False, str(e)
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
