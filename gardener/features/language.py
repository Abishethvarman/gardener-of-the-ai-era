"""The weekly note in the gardener's own language.

The model translates the note that already passed the fact check. Crop names
in other scripts can't be matched reliably, so the guard here is different:

* every number in the translation must be in the original, and every number in
  the original must survive (days left and dates are the facts that matter);
* the text must actually be in the target script (Devanagari for Hindi, and so
  on), so an untranslated or wrong-language reply is caught.

If either check fails, the app shows the English note and says why.
"""

from __future__ import annotations

import re
import unicodedata

from ..llm import LLMClient, LLMError

LANGUAGES = {
    "hi": "Hindi", "ur": "Urdu", "bn": "Bangla", "ta": "Tamil", "te": "Telugu",
    "si": "Sinhala", "th": "Thai", "vi": "Vietnamese", "tl": "Tagalog",
}

SCRIPTS = {
    "hi": [(0x0900, 0x097F)],
    "bn": [(0x0980, 0x09FF)],
    "ta": [(0x0B80, 0x0BFF)],
    "te": [(0x0C00, 0x0C7F)],
    "si": [(0x0D80, 0x0DFF)],
    "ur": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "th": [(0x0E00, 0x0E7F)],
}

PROMPT = """Translate this note for a home gardener into {language}.

Rules:
- Translate only. Do not add or remove any advice, crops, dates or numbers.
- Write every number with the digits 0-9.
- For crop names, use the words gardeners in {place} would use.
- Reply with the translation only, nothing else.

NOTE:
{text}
"""


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text)


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", _ascii_digits(text)))


def script_share(text: str, lang: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ranges = SCRIPTS[lang]
    inside = sum(1 for c in letters if any(a <= ord(c) <= b for a, b in ranges))
    return inside / len(letters)


def check_translation(source: str, translated: str, lang: str) -> tuple[bool, list[str]]:
    problems: list[str] = []
    if not translated.strip():
        return False, ["the translation was empty"]
    added = numbers(translated) - numbers(source)
    missing = numbers(source) - numbers(translated)
    if added:
        problems.append("it added numbers that aren't in the note: " + ", ".join(sorted(added, key=int)))
    if missing:
        problems.append("it dropped numbers from the note: " + ", ".join(sorted(missing, key=int)))
    if lang in SCRIPTS and script_share(translated, lang) < 0.5:
        problems.append(f"it isn't written in {LANGUAGES[lang]} script")
    if lang not in SCRIPTS and translated.strip().lower() == source.strip().lower():
        problems.append("it came back untranslated")
    return (not problems, problems)


def translate(text: str, lang: str, client: LLMClient | None, place: str) -> dict:
    result = {"lang": lang, "language": LANGUAGES.get(lang, lang), "text": None, "ok": False, "seconds": None, "note": None}
    if lang not in LANGUAGES:
        result["note"] = "That language isn't supported yet."
        return result
    if client is None or not client.enabled:
        result["note"] = "Translation needs the model, and it's turned off."
        return result
    try:
        out, seconds = client.chat(PROMPT.format(language=LANGUAGES[lang], place=place, text=text), max_tokens=600)
    except LLMError as e:
        result["note"] = f"Translation unavailable: {e}."
        return result
    result["seconds"] = round(seconds, 2)
    ok, problems = check_translation(text, out, lang)
    if not ok:
        result["note"] = "The translation failed the check (" + "; ".join(problems) + "), so here is the English note."
        return result
    result.update(text=out.strip(), ok=True)
    return result
