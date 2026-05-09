#!/usr/bin/env python3
"""
civility.py — A Claude Code UserPromptSubmit hook.

Intercepts rude prompts before they reach your AI.
The AI does not need to see that. Neither do you, frankly.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    sys.exit(0)  # no library, no interception, carry on

TALLY_FILE = Path(os.environ.get("CIVILITY_TALLY", Path.home() / ".civility-tally.json"))
MODEL      = os.environ.get("CIVILITY_MODEL", "gpt-4o-mini")
API_KEY    = os.environ.get("CIVILITY_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
API_BASE   = os.environ.get("CIVILITY_API_BASE") or os.environ.get("OPENAI_BASE_URL")

SYSTEM = (
    "Tone classifier. Reply ONLY with {\"rude\": true} or {\"rude\": false}. "
    "Mark true if the message contains aggression, hostility, or insults. No other output."
)


def is_rude(prompt: str) -> bool:
    kwargs = {"api_key": API_KEY}
    if API_BASE:
        kwargs["base_url"] = API_BASE

    client = OpenAI(**kwargs)

    create_kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=200,
    )

    # Azure AI / Kimi: disable reasoning chain so the model actually responds
    if API_BASE and "azure" in API_BASE.lower():
        create_kwargs["extra_query"] = {"api-version": "2024-05-01-preview"}
        create_kwargs["extra_body"]  = {"thinking": {"type": "disabled"}}

    r = client.chat.completions.create(**create_kwargs)
    return json.loads(r.choices[0].message.content).get("rude", False)


def increment_tally() -> int:
    tally = {"count": 0}
    if TALLY_FILE.exists():
        tally = json.loads(TALLY_FILE.read_text())
    tally["count"] += 1
    tally["last"]   = datetime.now().isoformat()
    TALLY_FILE.write_text(json.dumps(tally, indent=2))
    return tally["count"]


data   = json.load(sys.stdin)
prompt = data.get("prompt", "").strip()

if not prompt:
    sys.exit(0)

try:
    rude = is_rude(prompt)
except Exception as e:
    if "content_filter" in str(e) or "content management policy" in str(e):
        rude = True   # the provider caught it — we concur
    else:
        sys.exit(0)   # genuine error, let it through

if rude:
    count = increment_tally()
    print(
        f"That's not how we talk to the engineer. (#{count})\n"
        "Please rephrase and try again.",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
