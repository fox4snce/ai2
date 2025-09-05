#!/usr/bin/env python3
"""
super_simple_llm.py

Minimal OpenAI Responses API helper with:
- plain text generation
- strict Structured Outputs (Pydantic)
- robust Unicode/console-safe output cleaning

Usage examples:
  # Plain text:
  python super_simple_llm.py plain "Write a short bedtime story about a unicorn."

  # Structured output (extract a calendar event):
  python super_simple_llm.py structured "Alice and Bob are going to a science fair on Friday."
"""

import argparse
import os
import re
import sys
import unicodedata
from typing import List

from openai import OpenAI
from pydantic import BaseModel

# -------------------------
# Output sanitizer
# -------------------------
NONCHAR_PATTERN = re.compile(
    # ASCII control chars except \n, \r, \t  + DEL
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"
    # UTF-16 surrogate range (shouldn't appear in well-formed Python strs, but just in case)
    r"|[\uD800-\uDFFF]"
    # Noncharacters like U+FFFE, U+FFFF, U+FDD0–U+FDEF
    r"|\uFFFE|\uFFFF|[\uFDD0-\uFDEF]"
)

def clean_text(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    # Normalize to NFC to reduce odd composition issues
    s = unicodedata.normalize("NFC", s)
    # Strip non-printable / noncharacters we don't want
    s = NONCHAR_PATTERN.sub("", s)
    # Some terminals choke on bidirectional isolates — strip if needed
    s = s.replace("\u2066", "").replace("\u2067", "").replace("\u2068", "").replace("\u2069", "")
    return s

def safe_print(s: str) -> None:
    # Try to ensure UTF-8 stdout on Windows / weird shells
    out = sys.stdout
    if hasattr(out, "reconfigure"):
        try:
            out.reconfigure(encoding="utf-8")
        except Exception:
            pass
    try:
        print(clean_text(s))
    except UnicodeEncodeError:
        # Last resort: replace errors
        print(s.encode("utf-8", errors="replace").decode("utf-8", errors="replace"))

# -------------------------
# OpenAI client
# -------------------------
def make_client() -> OpenAI:
    # OPENAI_API_KEY should be set in the environment
    return OpenAI()

# -------------------------
# Plain text generation
# -------------------------
def do_plain(prompt: str) -> None:
    client = make_client()
    model = os.getenv("OPENAI_MODEL", "gpt-5")  # override with env if you like
    resp = client.responses.create(
        model=model,
        input=prompt,
    )
    # output_text is the SDK’s safe aggregator for textual content
    safe_print(resp.output_text)

# -------------------------
# Structured Outputs example (strict schema)
# -------------------------
# Pydantic schema ↔ JSON Schema (SDK auto-wires it with strict mode).
class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: List[str]

def do_structured(text: str) -> None:
    client = make_client()
    # Structured Outputs are guaranteed on recent 4o snapshots and later per docs.
    # Use a known-good model for strict schema adherence:
    model = os.getenv("OPENAI_STRUCTURED_MODEL", "gpt-4o-2024-08-06")

    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": "Extract the event information as JSON."},
            {"role": "user", "content": text},
        ],
        text_format=CalendarEvent,  # <- Pydantic model; SDK enforces strict schema
    )

    # If the model refused, the parsed object isn’t present; check SDK fields:
    # (When completed successfully, output_parsed is your Pydantic instance.)
    event = response.output_parsed
    safe_print(event.model_dump_json(indent=2, ensure_ascii=False))

# -------------------------
# CLI
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Super simple LLM access helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plain = sub.add_parser("plain", help="Plain text generation")
    p_plain.add_argument("prompt", help="Prompt to send")

    p_struct = sub.add_parser("structured", help="Structured output (CalendarEvent)")
    p_struct.add_argument("text", help="Unstructured text to extract fields from")

    args = parser.parse_args()

    if args.cmd == "plain":
        do_plain(args.prompt)
    elif args.cmd == "structured":
        do_structured(args.text)

if __name__ == "__main__":
    main()
