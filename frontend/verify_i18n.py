#!/usr/bin/env python3
"""Verify that every static translation key exists in Spanish and English."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "src"
I18N = (ROOT / "i18n.tsx").read_text(encoding="utf-8")

used: set[str] = set()
for path in ROOT.glob("*.ts*"):
    if path.name == "i18n.tsx":
        continue
    source = path.read_text(encoding="utf-8")
    used.update(re.findall(r"\bt\(['\"]([^'\"]+)['\"]", source))
    used.update(re.findall(r"\btranslate\(['\"]([^'\"]+)['\"]", source))

spanish = I18N.split("es: {", 1)[1].split("\n  },\n  en: {", 1)[0]
english = I18N.split("\n  en: {", 1)[1].split("\n  },\n};", 1)[0]
spanish_keys = set(re.findall(r"'([^']+)':", spanish))
english_keys = set(re.findall(r"'([^']+)':", english))

missing_es = sorted(used - spanish_keys)
missing_en = sorted(used - english_keys)
different = sorted(spanish_keys ^ english_keys)

if missing_es or missing_en or different:
    if missing_es:
        print("Missing Spanish keys:", *missing_es, sep="\n- ")
    if missing_en:
        print("Missing English keys:", *missing_en, sep="\n- ")
    if different:
        print("Dictionary mismatch:", *different, sep="\n- ")
    raise SystemExit(1)

print(f"Internationalization keys: PASS ({len(used)} used, {len(spanish_keys)} available)")
