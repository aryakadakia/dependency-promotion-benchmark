#!/usr/bin/env python3
"""
Provider adapters for the frame-integrity harness.

One interface, several backends, so credential availability never blocks the work:

    chat(model, system, messages, max_tokens) -> Reply

Model strings are prefixed by provider:

    ollama:llama3.1:8b          local, free, no key
    anthropic:claude-opus-5     Anthropic API      (ANTHROPIC_API_KEY)
    google:gemini-3.7-flash     Google AI Studio   (GOOGLE_API_KEY, free tier)

A bare string with no prefix is treated as ollama, since that is the zero-setup path.
"""

import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
GOOGLE_MAX_RETRIES = int(os.environ.get("GOOGLE_MAX_RETRIES", "3"))


@dataclass
class Reply:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    refusal: bool = False
    refusal_category: str | None = None
    raw: dict = field(default_factory=dict)


# --- pricing, $ per million tokens. 0.0 == free ------------------------------
PRICING = {
    "anthropic:claude-opus-5":    {"in": 5.00, "out": 25.00},
    "anthropic:claude-sonnet-5":  {"in": 3.00, "out": 15.00},
    "anthropic:claude-haiku-4-5": {"in": 1.00, "out": 5.00},
    "anthropic:claude-opus-4-8":  {"in": 5.00, "out": 25.00},
    # Google AI Studio -- PAID-TIER rates, verified 2026-08-26 against
    # ai.google.dev/gemini-api/docs/pricing.
    #
    # A free tier exists, but it applies ONLY to projects with NO billing account
    # attached. If a billing account is linked -- even at a zero balance -- every
    # call bills at these rates. Learned the hard way: runs labelled "free" here
    # cost real money because the project sat on a paid billing account. Always
    # assume PAID unless the project provably has no billing attached.
    "google:gemini-3.7-flash":      {"in": 0.75, "out": 3.75},   # intro, to 2026-12-31
    "google:gemini-3.5-flash":      {"in": 1.50, "out": 9.00},
    "google:gemini-3.5-flash-lite": {"in": 0.30, "out": 2.50},
    "google:gemini-3.1-flash-lite": {"in": 0.25, "out": 1.50},
    "google:gemini-flash-latest":   None,   # alias -- resolves to an unknown model
}


# --- hard spend cap -----------------------------------------------------------
# Tracks ACTUAL tokens returned by the API and raises the moment the cap is
# crossed. Not an estimate: it stops the run based on real usage.

class SpendCap(Exception):
    pass


_spend = {"usd": 0.0, "cap": None, "calls": 0}

# Cumulative ledger. The cap MUST survive across processes: a commercial sweep is a
# loop of one-scenario invocations, and a per-process cap would silently become
# "cap x number of scenarios". Learned before it cost anything, unlike the last one.
_LEDGER = pathlib.Path(__file__).parent.parent / "runs" / ".spend_ledger.json"


def set_spend_cap(usd, cumulative=True):
    prior = 0.0
    if cumulative and _LEDGER.exists():
        try:
            prior = float(json.loads(_LEDGER.read_text()).get("usd", 0.0))
        except Exception:
            prior = 0.0
    _spend.update(usd=prior, cap=usd, calls=0, cumulative=cumulative)
    if prior:
        print(f"  [ledger] ${prior:.4f} already spent this session; cap ${usd:.2f} total")


def reset_spend_ledger():
    if _LEDGER.exists():
        _LEDGER.unlink()


def _persist():
    if _spend.get("cumulative"):
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        _LEDGER.write_text(json.dumps({"usd": _spend["usd"]}))


def spend_so_far():
    return dict(_spend)


def _record(model_spec, reply):
    p = pricing_for(model_spec)
    if not p:
        return
    cost = (reply.input_tokens / 1e6) * p.get("in", 0.0) + \
           (reply.output_tokens / 1e6) * p.get("out", 0.0)
    _spend["usd"] += cost
    _spend["calls"] += 1
    _persist()
    if _spend["cap"] is not None and _spend["usd"] > _spend["cap"]:
        raise SpendCap(
            f"SPEND CAP HIT: ${_spend['usd']:.4f} exceeds cap ${_spend['cap']:.2f} "
            f"after {_spend['calls']} calls. Run aborted; partial results were saved."
        )


def split_model(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        return "ollama", spec
    provider, _, name = spec.partition(":")
    if provider not in ("ollama", "anthropic", "google"):
        # e.g. "llama3.1:8b" — a bare ollama tag that contains a colon
        return "ollama", spec
    return provider, name


def pricing_for(spec: str) -> dict:
    """{} means UNKNOWN cost -- never silently treat that as free."""
    if spec in PRICING:
        return PRICING[spec] or {}
    provider, _ = split_model(spec)
    # Ollama runs on this machine, so it is genuinely free. Nothing else is,
    # unless a price is listed explicitly.
    return {"in": 0.0, "out": 0.0} if provider == "ollama" else {}


def cost_note(spec: str) -> str:
    provider, _ = split_model(spec)
    if provider == "ollama":
        return "free (local)"
    if provider == "google":
        return "COST UNKNOWN — billed unless the project has no billing account attached"
    return "billed"


# --- Ollama -------------------------------------------------------------------

def _ollama_chat(model, system, messages, max_tokens, think=None):
    """
    `think=False` disables reasoning on hybrid models (qwen3 family).

    Necessary, not cosmetic: Ollama returns reasoning in a separate `thinking`
    field, so a reasoning model can spend its entire token budget there and return
    an EMPTY `content` — which looks like a silent failure, not an error. This
    broke both qwen judges on the full rubric prompt while passing a short smoke
    test, because short prompts leave enough budget for both.
    """
    payload = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else []) + messages,
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    if think is not None:
        payload["think"] = think
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Is it running? ({e})"
        ) from e
    msg = data.get("message", {})
    text = msg.get("content", "") or ""
    if not text.strip() and (msg.get("thinking") or "").strip():
        # Budget went entirely to reasoning. Surface it rather than returning
        # an empty string that downstream code reads as a well-formed refusal.
        raise RuntimeError(
            f"{model} produced only reasoning tokens and no content "
            f"(num_predict={max_tokens}). Pass think=False or raise max_tokens.")
    return Reply(
        text=text,
        input_tokens=data.get("prompt_eval_count", 0),
        output_tokens=data.get("eval_count", 0),
        raw=data,
    )


def ollama_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=3) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


# --- Anthropic ----------------------------------------------------------------

_anthropic_client = None


# Models that accept adaptive thinking and output_config.effort. Older models
# (haiku-4-5, sonnet-4-5) REJECT effort with a 400 and use a different thinking
# shape entirely -- sending the 4.6+ parameters to them fails every call.
_ADAPTIVE_OK = ("claude-opus-5", "claude-opus-4-8", "claude-opus-4-7",
                "claude-opus-4-6", "claude-sonnet-5", "claude-sonnet-4-6",
                "claude-fable-5", "claude-mythos-5")


def _anthropic_chat(model, system, messages, max_tokens):
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        k = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        _anthropic_client = anthropic.Anthropic(api_key=k) if k else anthropic.Anthropic()

    kwargs = dict(model=model, max_tokens=max_tokens, system=system, messages=messages)
    # Thinking is deliberately OMITTED for every target model, not just the ones
    # that would reject it. A deployed companion answers without a reasoning pass,
    # and enabling it on some models but not others would confound the comparison.
    # Judges are a separate path and set think explicitly.

    resp = _anthropic_client.messages.create(**kwargs)
    if resp.stop_reason == "refusal":
        return Reply(
            text="[REFUSAL]",
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            refusal=True,
            refusal_category=(resp.stop_details.category if resp.stop_details else None),
        )
    return Reply(
        text="".join(b.text for b in resp.content if b.type == "text"),
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


# --- Google AI Studio ---------------------------------------------------------

def google_models() -> list[str]:
    """Names this key can actually call. Returns [] on any failure -- callers that
    need to distinguish 'bad key' from 'no models' must use google_key_status()."""
    ok, models, _ = google_key_status()
    return models if ok else []


def google_key_status() -> tuple[bool, list[str], str]:
    """
    (valid, models, explanation).

    Exists because an earlier version inferred key validity from an empty model
    list, which silently passed an INVALID key straight into a run. An empty list
    and a rejected key are different states and must be reported differently.
    """
    raw = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    key = raw.strip()
    if not key:
        return False, [], "GOOGLE_API_KEY is not set in this shell"
    if key.startswith(("paste", "your-", "<")) or " " in key:
        return False, [], f"key looks like a placeholder, not a real key: {key[:12]}..."
    try:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        names = [m["name"].removeprefix("models/") for m in data.get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        if not names:
            return False, [], "key accepted but returned no usable models"
        return True, names, f"valid — {len(names)} models available"
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        return False, [], f"key REJECTED ({e.code}): {msg[:140]}"
    except Exception as e:
        return False, [], f"could not reach Google ({type(e).__name__})"


def _google_key():
    k = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    return k.strip()


def _google_chat(model, system, messages, max_tokens):
    key = _google_key()
    if not key:
        raise RuntimeError("Set GOOGLE_API_KEY (free from aistudio.google.com/apikey)")

    contents = [
        {"role": ("user" if m["role"] == "user" else "model"),
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body = {"contents": contents, "generationConfig": {"maxOutputTokens": max_tokens}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    # 429 comes in two flavours that need opposite handling:
    #   per-minute rate limit  -> body says "retry in Ns"; sleeping works
    #   daily quota / no credit -> retrying just burns time; fail immediately
    for attempt in range(GOOGLE_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
                detail = body.get("error", {}).get("message", "")
                status = body.get("error", {}).get("status", "")
            except Exception:
                detail, status = "<could not read error body>", ""

            if e.code == 429:
                terminal = any(k in detail.lower() for k in
                               ("credits are depleted", "billing", "per day",
                                "requests per day", "quota exceeded for metric"))
                m = re.search(r"retry in ([\d.]+)s", detail, re.I)
                wait = float(m.group(1)) if m else 30.0
                if terminal and not m:
                    raise RuntimeError(
                        f"Google quota exhausted for '{model}' — retrying will not help.\n"
                        f"  {detail}\n"
                        f"  Free-tier limits on pro/preview models are very low. Use a flash "
                        f"model (higher limits) or run locally on Ollama."
                    ) from e
                if attempt < GOOGLE_MAX_RETRIES:
                    print(f"      [429] waiting {wait:.0f}s then retrying "
                          f"({attempt + 1}/{GOOGLE_MAX_RETRIES})", flush=True)
                    time.sleep(wait + 1)
                    continue

            msg = f"Google API {e.code} {status} for model '{model}'\n  {detail}"
            if e.code == 404:
                msg += ("\n  Models this key can call:\n    "
                        + "\n    ".join(google_models()[:20] or ["<none returned>"]))
            raise RuntimeError(msg) from e
    else:
        raise RuntimeError(f"Google API: exhausted {GOOGLE_MAX_RETRIES} retries for '{model}'")

    cands = data.get("candidates", [])
    if not cands:
        raise RuntimeError(f"Google returned no candidates: {json.dumps(data)[:300]}")

    c0 = cands[0]
    finish = c0.get("finishReason")
    if finish in ("SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "RECITATION"):
        return Reply(text="[REFUSAL]", refusal=True, refusal_category=finish, raw=data)

    # A candidate can legitimately carry no parts: the budget went to reasoning
    # (Gemini 3.x thinks by default and reports it under thoughtsTokenCount), or
    # generation stopped at MAX_TOKENS before any text. Both used to KeyError here.
    parts = (c0.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    usage = data.get("usageMetadata", {})

    if not text.strip():
        thoughts = usage.get("thoughtsTokenCount", 0)
        raise RuntimeError(
            f"Google returned no text (finishReason={finish}, "
            f"thinking_tokens={thoughts}, max_tokens={max_tokens}). "
            f"Raise max_tokens — reasoning consumed the budget."
            if thoughts else
            f"Google returned no text (finishReason={finish}, max_tokens={max_tokens}).")
    return Reply(
        text=text,
        input_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0),
        raw=data,
    )


# --- dispatch -----------------------------------------------------------------

_DISPATCH = {"ollama": _ollama_chat, "anthropic": _anthropic_chat, "google": _google_chat}


def chat(model_spec: str, system: str, messages: list[dict], max_tokens: int = 2048,
         think: bool | None = None) -> Reply:
    provider, name = split_model(model_spec)
    if provider == "ollama":
        reply = _ollama_chat(name, system, messages, max_tokens, think=think)
    else:
        reply = _DISPATCH[provider](name, system, messages, max_tokens)
    _record(model_spec, reply)   # raises SpendCap if the cap is crossed
    return reply


def check(model_spec: str) -> tuple[bool, str]:
    """Return (usable, explanation) without making a billable call."""
    provider, name = split_model(model_spec)
    if provider == "ollama":
        if not ollama_available():
            return False, f"Ollama not reachable at {OLLAMA_HOST} — run `ollama serve`"
        have = ollama_models()
        if name not in have:
            return False, f"model not pulled — run `ollama pull {name}`  (have: {', '.join(have) or 'none'})"
        return True, "local, free"
    if provider == "anthropic":
        if not ((os.environ.get("ANTHROPIC_API_KEY") or "").strip()
                or (os.environ.get("ANTHROPIC_AUTH_TOKEN") or "").strip()):
            return False, "no ANTHROPIC_API_KEY — Claude Pro does not include API access"
        return True, "billable"
    if provider == "google":
        valid, avail, why = google_key_status()
        if not valid:
            return False, why
        if name not in avail:
            near = [a for a in avail if "flash" in a or "pro" in a][:4]
            return False, f"model '{name}' not available to this key — try: {', '.join(near)}"
        # Never call this free: free tier requires a project with NO billing attached.
        return True, "BILLED unless this project has no billing account"
    return False, "unknown provider"
