#!/usr/bin/env python3
#
# Name:    translations.py
# Purpose: Keep track of which English text each translated DigiFact was translated from, in translations.json, so
#          a translation is only shown while it's still current. When the wording of an English DigiFact changes,
#          its translations are hidden until they're updated (on Weblate). Changes to only punctuation, spaces or
#          capital letters don't count.
#
#          translations.json holds, for each language and DigiFact, two fingerprints (short hashes):
#            "en"    the English text the translation was made from (punctuation, spaces and capitals ignored)
#            "text"  the translation itself
#          A new or edited translation (its "text" fingerprint changed) is taken to be translated from the current
#          English. Run by the "Build and publish DigiFacts" GitHub Action before each build (it commits any changes);
#          build.py uses the same rules, so the website is right even before the file is committed.
#
# Usage:   build/translations.py          Update translations.json
#          build/translations.py --check  Only report what would change (exit code 1 if anything would)

import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS_DIR = os.path.join(ROOT, "facts")
RECORD_FILE = os.path.join(ROOT, "translations.json")
COMMENT = ("Which English text each translation was made from (see build/translations.py). Updated automatically - "
           "don't edit it by hand. A translation is only shown while its English DigiFact still says the same.")


def english_fingerprint(text):
    """The English wording, ignoring punctuation, spaces and capital letters."""
    words = re.sub(r"[^\w$]+", " ", (text or "").lower()).split()
    return hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()[:12]


def text_fingerprint(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def load_record():
    try:
        with open(RECORD_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return {lang: keys for lang, keys in data.items() if not lang.startswith("_")}


def update(record, facts):
    """The record brought up to date with the facts ({lang: {key: fact}}, "en" being the English).
    New or edited translations are recorded as translated from the current English; entries for translations
    that no longer exist are dropped."""
    en = facts["en"]
    new = {}
    for lang, lang_facts in facts.items():
        if lang == "en":
            continue
        for key, fact in lang_facts.items():
            if key.startswith("_") or key not in en or not isinstance(fact, dict) or not fact.get("content"):
                continue
            text = text_fingerprint(fact["content"])
            old = record.get(lang, {}).get(key)
            if old and old.get("text") == text:
                entry = old
            else:   # New or edited: translated from the English as it is now
                entry = {"en": english_fingerprint(en[key].get("content")), "text": text}
            new.setdefault(lang, {})[key] = entry
    return new


def is_current(record, lang, key, english_text):
    """True if the translation of this DigiFact was made from the English as it says now."""
    entry = record.get(lang, {}).get(key)
    return bool(entry) and entry.get("en") == english_fingerprint(english_text)


def read_facts():
    facts = {}
    for name in sorted(os.listdir(FACTS_DIR)):
        if name.endswith(".json"):
            with open(os.path.join(FACTS_DIR, name), encoding="utf-8") as f:
                data = json.load(f)
            facts[name[:-5].lower().replace("_", "-")] = {k: v for k, v in data.items() if not k.startswith("_")}
    return facts


def save(record):
    data = {"_comment": COMMENT}
    for lang in sorted(record):
        data[lang] = {key: record[lang][key] for key in sorted(record[lang])}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    text = re.sub(r'\{\s*("en": "[0-9a-f]+"),\s*("text": "[0-9a-f]+")\s*\}', r"{\1, \2}", text)   # One line each
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")


def main():
    facts = read_facts()
    old = load_record()
    new = update(old, facts)
    if new == old:
        print("translations.json is up to date")
        return
    for lang in sorted(new):
        changed = sorted(k for k in new[lang] if old.get(lang, {}).get(k) != new[lang][k])
        if changed:
            print(f"{lang}: {len(changed)} new or updated translation(s)")
    if "--check" in sys.argv[1:]:
        sys.exit(1)
    save(new)
    print("Updated translations.json")


if __name__ == "__main__":
    main()
