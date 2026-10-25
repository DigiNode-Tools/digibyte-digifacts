#!/usr/bin/env python3
#
# Name:    build.py
# Purpose: Build the DigiFacts website (https://digifacts.diginode.tools) from the facts in facts/<lang>.json.
#          Run hourly by the "Build and publish DigiFacts" GitHub Action, and whenever the facts change.
#
#          1. Checks every facts file (a broken file stops the build, so the live site is never broken).
#          2. Gets the current DigiByte block count from several block explorers. It uses the middle value of the
#             ones that look right, never goes backwards, and falls back to an estimate (one block every 15
#             seconds) if no explorer answers.
#          3. Numbers the facts in the order they appear in facts/en.json (so deleting one never leaves a gap - a
#             DigiFact's permanent ID is its key, e.g. digifact-7ttm), makes each title from the language's "_title"
#             (e.g. "DigiFact #{number}"), fills in the live values (e.g. $blocks_tot_mil) and writes each language in each format (social, html, markdown),
#             plus languages.json, info.json, and the help and proofreading pages. Each language only has the facts
#             with a current translation: a fact that isn't translated, or whose English wording has changed since
#             it was translated (see build/translations.py), is left out until it's translated.
#          4. Picks the DigiFact of the day (every fact once before any repeats) and writes <lang>/today.json and an
#             RSS feed of the last 30 days, <lang>/feed.xml.
#
#          Everything here is public, so anyone can see exactly how DigiFacts are made.
#
# Usage:   build/build.py OUT_DIR
#          Environment (optional):
#            DIGIFACTS_SITE_URL   Where the site is published, to read the previous info.json (block count never
#                                 goes backwards, and the build can tell whether anything changed)
#            GITHUB_OUTPUT        Set by GitHub Actions: 'changed=true|false' is written to it
#            FORCE_PUBLISH=1      Report changed=true even if nothing changed
#            GOATCOUNTER_API_KEY  A read-only GoatCounter API key: publishes the link click stats (stats/, stats.json
#                                 and the clicks on the proofreading pages). Without it there are no click stats.

import email.utils
import hashlib
import html
import json
import os
import random
import re
import shutil
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translations   # noqa: E402  (build/translations.py)
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS_DIR = os.path.join(ROOT, "facts")
TAGS_FILE = os.path.join(ROOT, "tags.json")   # Topics, so sites can hide DigiFacts about themselves
WEBLATE_URL = "https://hosted.weblate.org/engage/digibyte-digifacts/"
REPO_URL = "https://github.com/DigiNode-Tools/digibyte-digifacts"
SITE_URL = "https://digifacts.diginode.tools"
# Short links for facts with a link, on go.diginode.tools (DigiNode Tools' short links - the DigiNode-Tools/go repo):
# the four characters of the fact's ID, e.g. https://go.diginode.tools/7ttm. Every format, the DigiFact of the day
# and the RSS feed use them instead of the full address - shorter for posts and small displays, and every click
# on a DigiFact's link is counted. Add the full address to a DigiFact; the build shortens it. (The proofreading
# pages show the full address, for checking it.) The build publishes each short link's page (redirect, preview
# card, click counting) in short-links.json, which go.diginode.tools copies every hour.
GO_URL = "https://go.diginode.tools/"
# In capitals for QR codes (e.g. HTTPS://GO.DIGINODE.TOOLS/7TTM): a QR code can then use its compact alphanumeric
# mode, so it's small enough for a 64x32 display (25x25). Not the whole ID: the link has to fit in the QR code.
GO_QR_URL = GO_URL.upper()
# The short links DigiFacts uses. Until go.diginode.tools was set up they were on this site (/l/7ttm and /L/7TTM),
# and those pages are still published, so links shared then keep working.
SHORT_LINKS_ON_GO = True
SHORT_BASE = GO_QR_URL if SHORT_LINKS_ON_GO else SITE_URL.upper() + "/L/"
SHORT_TEXT_BASE = GO_URL if SHORT_LINKS_ON_GO else SITE_URL + "/l/"
# Third-party link shorteners aren't allowed: their links can expire (and some have), and they hide where a link goes
SHORTENERS = {"bit.ly", "j.mp", "rb.gy", "t.ly", "tinyurl.com", "is.gd", "t.co", "ow.ly", "buff.ly", "goo.gl",
              "cutt.ly", "shorturl.at", "rebrand.ly", "tiny.cc", "v.gd", "s.id"}
SPONSOR_URL = "https://diginode.tools/sponsors/"
# Clicks on the short links are counted with GoatCounter (open source, no cookies, no personal data). Each fact is
# counted under its ID, so its history stays together when its number changes; QR code scans (the capital L/ links)
# have the referrer "QR code".
STATS_URL = "https://digifacts.goatcounter.com"
# The preview cards shown when a DigiFacts link is shared (cards/: the PNGs, and the HTML they were drawn from).
# Each DigiFact always uses the same one (chosen by its ID), so a feed of DigiFacts alternates between them.
CARDS = ["cards/card-1.png", "cards/card-2.png"]
# Tags that say where a short link was shown, e.g. https://go.diginode.tools/7ttm?dnt - counted as the click's source
# ("DigiNode Tools"). Any other tag is counted as itself. QR codes can't contain "?" (they'd lose their compact
# mode) - the capitals links count as "QR code" instead.
SOURCE_TAGS = {"dnt": "DigiNode Tools", "bsky": "Bluesky", "tg": "Telegram", "x": "X"}
USER_AGENT = f"DigiFacts builder ({REPO_URL})"

LANGUAGE_NAMES = {
    "en": "English", "en-gb": "English (UK)", "pt-br": "Portuguese (Brazil)", "de": "German", "es": "Spanish", "fr": "French", "hi": "Hindi", "it": "Italian",
    "ja": "Japanese", "ko": "Korean", "nl": "Dutch", "pt": "Portuguese", "ru": "Russian",
    "zh": "Chinese (Simplified)",
}
FIELDS = ("content", "url", "link_social", "link_html", "link_md")
TITLE_KEY = "_title"   # Each language's title, e.g. "DigiFact #{number}"
# A DigiFact's ID (its key): "digifact-" and four random characters, e.g. digifact-7ttm - so it can't be mistaken
# for the DigiFact's number. build/new_id.py makes a new one (no vowels, so an ID can't spell a word; no 0, 1 or l;
# never two numbers in a row).
ID_RE = re.compile(r"digifact-[a-z0-9]{4}")
FORMATS = {"social": "link_social", "html": "link_html", "markdown": "link_md"}
OUTPUT_FORMATS = dict(FORMATS, plain=None)   # plain = the fact without its link (e.g. for small displays)

# The only HTML allowed in a fact: one link, in link_html. (Sites may show the html format as HTML.)
LINK_HTML_RE = re.compile(r'[^<>]*<a target="_blank" href="https://[^"<>\s]+">[^<>]+</a>[^<>]*')

# Block count. A reading is only used if it's within 3% of the estimate below (one block every 15 seconds since
# a known block), and never lower than the last published count.
BLOCK_TIME = 15
ANCHOR_HEIGHT, ANCHOR_TIME = 24372532, 1791825343   # 2026-10-12 17:15 UTC
SANE_RANGE = 0.03


def explorer_chainz():
    return int(fetch("https://chainz.cryptoid.info/dgb/api.dws?q=getblockcount").strip())


def explorer_digibyte_io():
    return int(json.loads(fetch("https://digibyte.io/api/getblockchaininfo"))["blocks"])


def explorer_atomic_blockbook():
    d = json.loads(fetch("https://digibyte.atomicwallet.io/api/"))["blockbook"]
    if not d.get("inSync"):
        raise ValueError("not in sync")
    return int(d["bestHeight"])


EXPLORERS = {
    "chainz.cryptoid.info": explorer_chainz,
    "digibyte.io": explorer_digibyte_io,
    "digibyte.atomicwallet.io": explorer_atomic_blockbook,
}

# Live values that can be used in a fact. Longer names first, so $blocks_tot_mil isn't read as $blocks_tot.
VARIABLES = {
    "$blocks_tot_mil": lambda n: f"{n // 1000000}.{(n % 1000000) // 100000}",   # 24.3 (rounded down)
    "$blocks_tot_cs": lambda n: f"{n:,}",                                       # 24,372,532
    "$blocks_tot": lambda n: str(n),                                            # 24372532
}
VARIABLE_RE = re.compile(r"\$[a-z_]+")


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def warn(msg):
    print(f"::warning::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"WARNING: {msg}")


def fail(msg):
    sys.exit(f"::error::{msg}" if os.environ.get("GITHUB_ACTIONS") else f"ERROR: {msg}")


# ---------------------------------------------------------------------------------------------------------------
# 1. Read and check the facts

def no_duplicate_keys(pairs):
    """json.load would quietly keep only the last of two DigiFacts with the same ID - so stop instead."""
    data = {}
    for key, value in pairs:
        if key in data:
            raise KeyError(key)
        data[key] = value
    return data


def load_facts():
    """Return ({lang: {key: fact}}, {lang: title}) in language order (English first), checking everything.
    Exits on a problem."""
    # Language files are named with their language code: de.json, or e.g. pt_BR.json / pt-br.json for a regional
    # variant (Weblate names new files pt_BR.json). On the website the code is lower case with a hyphen: pt-br.
    files = {}
    for name in os.listdir(FACTS_DIR):
        if name.endswith(".json"):
            code = name[:-5]
            if not re.fullmatch(r"[a-z]{2,3}([_-][A-Za-z0-9]{2,4})?", code):
                fail(f"facts/{name}: name the file with a language code, e.g. de.json or pt_BR.json")
            files[code.lower().replace("_", "-")] = name
    langs = sorted(files, key=lambda l: (l != "en", l))
    if "en" not in langs:
        fail("facts/en.json is missing")
    facts, titles = {}, {}
    for lang in langs:
        path = f"facts/{files[lang]}"
        if lang not in LANGUAGE_NAMES:
            warn(f"{path}: add the language's name to LANGUAGE_NAMES in build/build.py")
            LANGUAGE_NAMES[lang] = lang
        try:
            with open(os.path.join(FACTS_DIR, files[lang]), encoding="utf-8") as f:
                data = json.load(f, object_pairs_hook=no_duplicate_keys)
        except ValueError as e:
            fail(f"{path} is not valid JSON: {e}")
        except KeyError as e:
            fail(f'{path}: the key {e.args[0]} is used twice - every DigiFact needs a key of its own')
        if not isinstance(data, dict):
            fail(f"{path} should contain one object with a key for each DigiFact")
        title = data.pop(TITLE_KEY, "")
        if title:
            if not isinstance(title, str) or title.count("{number}") != 1 or re.search(r"[<>$]", title):
                fail(f'{path} {TITLE_KEY} should be text containing {{number}} once, e.g. "DigiFact #{{number}}"')
            titles[lang] = title
        for key, fact in data.items():
            where = f"{path} {key}"
            if not ID_RE.fullmatch(key):
                fail(f"{where}: each DigiFact's key is its ID, e.g. digifact-7ttm (a new DigiFact's key is replaced by "
                     f"its ID automatically - see build/assign_ids.py)")
            if not isinstance(fact, dict):
                fail(f"{where} should be an object")
            for field, value in fact.items():
                if field not in FIELDS:
                    hint = f" - titles are now set once per language, with {TITLE_KEY}" if field == "title" else ""
                    fail(f"{where}: unknown field '{field}' (allowed: {', '.join(FIELDS)}){hint}")
                if not isinstance(value, str):
                    fail(f"{where} {field} should be text")
                if field != "link_html" and re.search(r"[<>]", value):
                    fail(f"{where} {field}: '<' and '>' aren't allowed (only link_html may contain a link)")
                for var in VARIABLE_RE.findall(value):
                    if var not in VARIABLES:
                        fail(f"{where} {field}: unknown live value '{var}' (available: {', '.join(VARIABLES)})")
            if fact.get("link_html") and not LINK_HTML_RE.fullmatch(fact["link_html"]):
                fail(f'{where} link_html should contain exactly one link: <a target="_blank" href="https://...">text</a>')
            if fact.get("url") and not re.fullmatch(r"https://\S+", fact["url"]):
                fail(f"{where} url should start with https://")
            if fact.get("url") and urllib.parse.urlparse(fact["url"]).netloc.lower() in SHORTENERS:
                fail(f"{where} url: use the full address, not a link shortener - the build makes a short link for it")
        facts[lang] = data

    en = facts["en"]
    if "en" not in titles:
        fail(f"facts/en.json needs a {TITLE_KEY}")
    for key, fact in en.items():
        if not fact.get("content"):
            fail(f"facts/en.json {key} needs content")
        if fact.get("url"):
            for field in ("link_social", "link_html", "link_md"):
                if fact["url"] not in fact.get(field, ""):
                    fail(f"facts/en.json {key} {field} should contain the url")
    for lang in langs[1:]:
        for key, fact in facts[lang].items():
            if key not in en:
                warn(f"facts/{files[lang]} {key} isn't in facts/en.json - it will be ignored (build/tidy.py removes it)")
                continue
            if fact.get("content"):
                if set(VARIABLE_RE.findall(en[key]["content"])) != set(VARIABLE_RE.findall(fact["content"])):
                    warn(f"facts/{files[lang]} {key} content should use the same live values as English: "
                         f"{', '.join(sorted(set(VARIABLE_RE.findall(en[key]['content'])))) or 'none'}")
        if lang not in titles and lang.split("-")[0] not in titles:
            warn(f"facts/{files[lang]} has no {TITLE_KEY} - the English title is used")
    return facts, titles


def load_tags(en):
    """Return (tag descriptions {tag: description}, {fact id: [tags]}), checking tags.json against facts/en.json."""
    if not os.path.exists(TAGS_FILE):
        return {}, {}
    try:
        with open(TAGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError as e:
        fail(f"tags.json is not valid JSON: {e}")
    described = data.get("tags", {})
    fact_tags = {}
    for tag, desc in described.items():
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", tag) or not isinstance(desc, str):
            fail(f"tags.json: tag '{tag}' should be lower case letters, numbers and hyphens, with a description")
    for key, tags in data.get("facts", {}).items():
        if key not in en:
            warn(f"tags.json: {key} isn't in facts/en.json - ignored (build/tidy.py removes it)")
            continue
        if not isinstance(tags, list):
            fail(f"tags.json: {key} should have a list of tags")
        for tag in tags:
            if tag not in described:
                fail(f"tags.json: {key} uses '{tag}', which isn't described under \"tags\"")
        fact_tags[key] = sorted(set(tags))
    return described, fact_tags


def fallbacks(lang, facts):
    """The languages to take each DigiFact from, in order: e.g. en-gb -> en-gb, en; pt-br -> pt-br, pt.
    A language variant (e.g. British English) only needs the DigiFacts that differ from its main language. Other
    languages never fall back to English: a DigiFact without a current translation is left out."""
    chain = [lang]
    if "-" in lang and lang.split("-")[0] in facts:
        chain.append(lang.split("-")[0])
    if lang.split("-")[0] == "en" and "en" not in chain:
        chain.append("en")
    return chain


LINK_IN_TEXT_RE = re.compile(r"(?:https?:)?//[^\s<>\"')\]]+|www\.[^\s<>\"')\]]+", re.I)


# Web addresses and domain names in text (e.g. https://example.com, www.example.com, example.com)
DOMAIN_RE = re.compile(r"(?<![\w@.-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w-])", re.I)


def new_addresses(text, english):
    """Domain names in a translation that aren't in the English DigiFact - a translation mustn't add any (a social
    app would make them clickable)."""
    allowed = {d.lower() for d in DOMAIN_RE.findall(english)}
    return {d.lower() for d in DOMAIN_RE.findall(text)} - allowed


def safe_link(link, url):
    """True if every address in a link field is the DigiFact's own url (and there are none if it has no url)."""
    found = [a.rstrip(".,;:!?").rstrip("/") for a in LINK_IN_TEXT_RE.findall(link)]
    return all(a == url.rstrip("/") for a in found) and (bool(found) == bool(url and link))


def localise(facts, titles, lang, record):
    """The facts for one language, in English order, numbered as in English (DigiFact #12 is #12 in every language):
    the translation where there is a current one (for a language variant, its own version or else its main
    language's). A DigiFact without a current translation is left out (English and its variants have every fact).
    Each fact gets its title, from the language's title (or its main language's, or the English one) and its number.
    Returns (facts, status): status is {key: "translated" | "outdated" | "missing"} for every DigiFact."""
    en = facts["en"]
    chain = fallbacks(lang, facts)
    title = next((titles[l] for l in chain if l in titles), titles["en"])
    out, status = {}, {}
    for number, key in enumerate(en, start=1):
        source = None
        for l in chain:
            if facts[l].get(key, {}).get("content") and (l == "en" or translations.is_current(record, l, key, en[key]["content"])):
                source = l
                break
        if source is None:
            translated_somewhere = any(facts[l].get(key, {}).get("content") for l in chain)
            status[key] = "outdated" if translated_somewhere else "missing"
            continue
        fact = dict(facts[source][key])
        if source != "en" and new_addresses(fact.get("content", ""), en[key]["content"]):
            warn(f"{source} {key}: the translation mentions a website the English DigiFact doesn't "
                 f"({', '.join(sorted(new_addresses(fact['content'], en[key]['content'])))}) - left out")
            status[key] = "missing"
            continue
        # A translation can change the words around a link, but never the link: it's always the English DigiFact's
        # address. (Anyone can translate, so a changed link could send people somewhere else.) If a translated link
        # field has any other address, that DigiFact uses its English links instead.
        fact["url"] = en[key].get("url", "")
        if source != "en" and not all(safe_link(fact.get(f, ""), fact["url"]) and
                                      not new_addresses(fact.get(f, ""), en[key].get(f, "") + " " + fact["url"])
                                      for f in FORMATS.values()):
            warn(f"{source} {key}: a link was changed in the translation - the English link is used instead "
                 f"(translations can't change a DigiFact's link)")
            for f in FORMATS.values():
                fact[f] = en[key].get(f, "")
        if en[key].get("url") and not all(fact.get(f) for f in FORMATS.values()):
            for f in FORMATS.values():   # Translated text, but no translated link yet: use the next language's link
                fact[f] = next((facts[l][key][f] for l in chain + ["en"] if facts[l].get(key, {}).get(f)), en[key].get(f, ""))
        out[key] = dict(fact, title=title.replace("{number}", str(number)), number=number, translated=source != "en" or lang == "en")
        status[key] = "translated"
    return out, status


# ---------------------------------------------------------------------------------------------------------------
# 2. Block count

def previous_info():
    site = os.environ.get("DIGIFACTS_SITE_URL", "").rstrip("/")
    if not site:
        return {}
    try:
        info = json.loads(fetch(f"{site}/info.json"))
        return info if isinstance(info, dict) else {}
    except Exception as e:
        print(f"No previous info.json ({e})")
        return {}


def block_count(prev):
    now = int(time.time())
    prev_count = prev.get("block_count") if isinstance(prev.get("block_count"), int) else 0
    prev_time = prev.get("block_count_time") if isinstance(prev.get("block_count_time"), int) else 0
    if prev_count and prev_time:
        estimate = prev_count + (now - prev_time) // BLOCK_TIME
    else:
        estimate = ANCHOR_HEIGHT + (now - ANCHOR_TIME) // BLOCK_TIME

    readings = {}
    for name, get in EXPLORERS.items():
        try:
            n = get()
        except Exception as e:
            warn(f"Block explorer {name} didn't answer: {e}")
            continue
        if abs(n - estimate) > estimate * SANE_RANGE:
            warn(f"Block explorer {name} says {n:,}, too far from the expected {estimate:,} - ignored")
            continue
        readings[name] = n
        print(f"Block explorer {name}: {n:,}")

    if readings:
        count = statistics.median_low(readings.values())
        source = ", ".join(sorted(readings))
    else:
        warn(f"No block explorer answered - using an estimate ({estimate:,})")
        count, source = estimate, "estimate"
    if count < prev_count:
        count = prev_count   # Never go backwards
    return count, source, now, readings


# ---------------------------------------------------------------------------------------------------------------
# 3. Link click stats (from GoatCounter - see STATS_URL)

STATS_SINCE = "2026-10-13"   # When counting began
STATS_DAYS = 30


def goatcounter(path, params, api_key):
    url = f"{STATS_URL}/api/v0/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT,
                                               "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:   # Too many requests: wait a moment
                time.sleep(2)
                continue
            raise RuntimeError(f"{path}: HTTP {e.code} {e.read()[:300].decode('utf-8', 'replace')}") from None


def click_stats(keys, prev_site):
    """{"facts": {id: {"clicks", "clicks_30_days", "qr"}}, "total", "referrers", "countries"} for the DigiFacts with
    links (keys), or None without an API key. If GoatCounter doesn't answer, the published stats are kept."""
    api_key = os.environ.get("GOATCOUNTER_API_KEY", "").strip()
    if not api_key:
        return None
    hour = time.strftime("%Y-%m-%dT%H:00:00Z", time.gmtime(time.time() + 3600))
    since_30 = time.strftime("%Y-%m-%dT%H:00:00Z", time.gmtime(time.time() - STATS_DAYS * 86400))
    try:
        def hits(start):
            got = goatcounter("stats/hits", {"start": start, "end": hour, "limit": 100}, api_key)
            return {h["path"]: h for h in got.get("hits", [])}
        all_time, recent = hits(STATS_SINCE + "T00:00:00Z"), hits(since_30)
        facts, total = {}, 0
        for key in keys:
            h = all_time.get("/" + key)
            clicks = h["count"] if h else 0
            qr = 0
            if clicks:
                time.sleep(0.3)   # GoatCounter allows a few requests a second
                refs = goatcounter(f"stats/hits/{h['path_id']}", {"start": STATS_SINCE + "T00:00:00Z", "end": hour,
                                                                    "limit": 100}, api_key)
                qr = sum(r["count"] for r in refs.get("refs", []) if "qr code" in str(r.get("name", "")).lower())
            facts[key] = {"clicks": clicks, "clicks_30_days": recent["/" + key]["count"] if "/" + key in recent else 0,
                          "qr": qr}
            total += clicks

        def top(page):
            got = goatcounter(f"stats/{page}", {"start": STATS_SINCE + "T00:00:00Z", "end": hour, "limit": 10}, api_key)
            return [{"name": r["name"] or "Direct (no referrer)", "clicks": r["count"]} for r in got.get("stats", [])]
        return {"since": STATS_SINCE, "facts": facts, "total": total, "referrers": top("toprefs"),
                "countries": top("locations")}
    except Exception as e:
        warn(f"Couldn't get the click stats from GoatCounter ({e}) - keeping the published ones")
        try:
            return json.loads(fetch(f"{prev_site}/stats.json")) if prev_site else None
        except Exception:
            return None


def stats_page(stats, en_facts, count):
    numbers = {key: n for n, key in enumerate(en_facts, start=1)}
    rows = []
    for key, s in sorted(stats["facts"].items(), key=lambda kv: (-kv[1]["clicks_30_days"], -kv[1]["clicks"], numbers.get(kv[0], 0))):
        if key not in en_facts:
            continue
        f = en_facts[key]
        text = fill(f["content"], count)
        text = text if len(text) <= 90 else text[:90].rsplit(" ", 1)[0] + "..."
        rows.append(f'<tr><td>{numbers[key]}</td><td>{html.escape(text)}<br><span class="muted"><code>{key}</code> · '
                    f'<a href="{html.escape(f["url"], quote=True)}">link</a></span></td>'
                    f'<td>{s["clicks_30_days"]:,}</td><td>{s["clicks"]:,}</td><td>{s["qr"]:,}</td></tr>')

    def top(items):
        return "".join(f"<li>{html.escape(i['name'])}: {i['clicks']:,}</li>" for i in items) or "<li>None yet</li>"
    since = time.strftime("%-d %B %Y", time.strptime(stats["since"], "%Y-%m-%d"))
    body = f"""<h1>DigiFacts link clicks</h1>
<p>How many people clicked each DigiFact's link (or scanned its QR code), counted since {since}: {stats["total"]:,} so far. Clicks are counted with <a href="https://www.goatcounter.com">GoatCounter</a> - no cookies and no personal data. Ad blockers stop some clicks being counted, so the real numbers are a little higher.</p>
<div class="scroll"><table>
<tr><th>#</th><th>DigiFact</th><th>Last {STATS_DAYS} days</th><th>All time</th><th>QR scans</th></tr>
{"".join(rows)}
</table></div>
<div class="row two">
<div><h2>Where clicks come from</h2><ul>{top(stats["referrers"])}</ul></div>
<div><h2>Countries</h2><ul>{top(stats["countries"])}</ul></div>
</div>
<p class="muted">Updated every hour. <a href="../stats.json">stats.json</a> · <a href="../">About DigiFacts</a></p>"""
    meta = preview_tags("DigiFacts link clicks", "Which DigiFacts people click on most.", CARDS[0], SITE_URL + "/stats/")
    return PAGE.format(lang="en", title="DigiFacts link clicks", body=body, meta=meta)


# ---------------------------------------------------------------------------------------------------------------
# 4. Output

FEED_DAYS = 30


def fact_of_the_day(keys, day):
    """The DigiFact for a day (days since 1970-01-01, UTC). The facts are shuffled into a new order each cycle, so
    every fact is shown once before any is repeated, and the same fact is chosen in every language."""
    def order(cycle):
        o = list(keys)
        random.Random(f"digifacts-{cycle}").shuffle(o)
        return o
    cycle, pos = divmod(day, len(keys))
    o = order(cycle)
    if len(o) > 1 and o[0] == order(cycle - 1)[-1]:
        o[0], o[1] = o[1], o[0]   # Don't show the same fact two days running, between cycles
    return o[pos]


def today_and_feed(lang, loc, count, day, fact_tags):
    """<lang>/today.json and <lang>/feed.xml (RSS) for one language."""
    keys = list(loc)   # Only the language's DigiFacts (fully translated languages have the same order as English)

    def entry(d):
        key = fact_of_the_day(keys, d)
        f = loc[key]
        return {
            "date": time.strftime("%Y-%m-%d", time.gmtime(d * 86400)),
            "number": f["number"],
            "key": key,
            "title": fill(f["title"], count),
            "url": f.get("url", ""),
            "text": fill(f["content"] + short_link(key, f, "link_social"), count),
            "html": fill(f["content"] + short_link(key, f, "link_html"), count),
            "markdown": fill(f["content"] + short_link(key, f, "link_md"), count),
            "plain": fill(f["content"], count),
            "short_url": short_url(key, f),
            "short_link": SHORT_TEXT_BASE + key[len("digifact-"):] if f.get("url") else "",
            "id": key,
            "tags": fact_tags.get(key, []),
        }

    today = entry(day)
    items = []
    for d in range(day, day - FEED_DAYS, -1):
        e = entry(d)
        items.append(
            "<item>"
            f"<title>{html.escape(e['title'])}</title>"
            f"<description>{html.escape(e['text'])}</description>"
            f"<link>{html.escape(e['short_link'] or SITE_URL + '/')}</link>"
            f"<guid isPermaLink=\"false\">digifacts-{lang}-{e['date']}</guid>"
            f"<pubDate>{email.utils.formatdate(d * 86400, usegmt=True)}</pubDate>"
            "</item>")
    feed = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>DigiByte DigiFacts ({html.escape(LANGUAGE_NAMES[lang])})</title>"
            f"<link>{SITE_URL}/</link>"
            "<description>A DigiFact - a bite-size fact about DigiByte - every day.</description>"
            f"<language>{lang}</language>"
            + "".join(items) + "</channel></rss>\n")
    return to_json(today), feed


def short_url(key, fact):
    return SHORT_BASE + key[len("digifact-"):].upper() if fact.get("url") else ""


def short_link(key, fact, field):
    """The fact's link field (link_social, link_html or link_md), with its short link (in lower case) instead of
    the full address."""
    link = fact.get(field, "")
    if not fact.get("url"):
        return link
    # The address, with or without a "/" at the end (e.g. https://example.com and https://example.com/)
    address = re.compile(re.escape(fact["url"].rstrip("/")) + r"/?(?![\w/?#%-])")
    return address.sub(lambda m: SHORT_TEXT_BASE + key[len("digifact-"):], link)


def preview_tags(title, description, image, page_url):
    """Open Graph and X tags, so a shared link shows a preview card."""
    tags = {"og:type": "website", "og:site_name": "DigiFacts", "og:title": title, "og:description": description,
            "og:url": page_url, "og:image": f"{SITE_URL}/{image}", "og:image:width": "1200", "og:image:height": "630",
            "og:image:alt": "DigiFacts - bite-size facts about DigiByte"}
    out = f'<meta name="description" content="{html.escape(description, quote=True)}">'
    out += "".join(f'<meta property="{k}" content="{html.escape(v, quote=True)}">' for k, v in tags.items())
    out += '<meta name="twitter:card" content="summary_large_image">'
    return out


def card_for(key):
    return CARDS[int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % len(CARDS)]


def redirect_page(url, key, title, qr, number=0, text=""):
    """A short link's page: counts the click (if the counter isn't blocked), then goes to the full address. It has
    its DigiFact's preview card, for when the link is shared (the sites that make previews don't follow the
    redirect)."""
    u = html.escape(url, quote=True)
    count = urllib.parse.urlencode({"p": "/" + key, "t": title, "r": "QR code" if qr else ""})
    script = (f"try{{var c={json.dumps(STATS_URL + '/count?' + count)};"
              + ("" if qr else
                 # Where the click came from: a tag on the link (e.g. ?dnt from DigiNode Tools - see SOURCE_TAGS), or
                 # else the website it was on
                 f"var v=(location.search.match(/^\\?([a-z0-9-]{{1,20}})/i)||[])[1],n={json.dumps(SOURCE_TAGS)};"
                 "if(v)c=c.replace('&r=','&r='+encodeURIComponent(n[v.toLowerCase()]||v));"
                 "else if(document.referrer)c=c.replace('&r=','&r='+encodeURIComponent(document.referrer));")
              + "c+='&rnd='+Math.random().toString(36).slice(2);"
              "if(navigator.sendBeacon)navigator.sendBeacon(c);else(new Image()).src=c}catch(e){}"
              f"location.replace({json.dumps(url)})").replace("</", "<\\/")
    domain = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    code = key[len("digifact-"):]
    preview = preview_tags(f"DigiFact #{number}", f"{text} Learn more on {domain}.", card_for(key),
                           (GO_QR_URL + code.upper()) if qr else (GO_URL + code))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>DigiFact #{number}</title><meta name="robots" content="noindex">{preview}'
            f'<meta http-equiv="refresh" content="0; url={u}"><script>{script}</script></head>'
            f'<body><p>Going to <a href="{u}">{u}</a></p></body></html>\n')


def fill(text, count):
    for var, value in VARIABLES.items():
        text = text.replace(var, value(count))
    return text


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def to_json(data):
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{meta}
<style>
:root {{ color-scheme: light dark; --fg: #1d2330; --muted: #5b6475; --bg: #fff; --card: #f4f7fb; --line: #d9e1ec; --accent: #0066cc; }}
@media (prefers-color-scheme: dark) {{ :root {{ --fg: #e6ebf2; --muted: #9aa6b8; --bg: #0f1520; --card: #172131; --line: #26344a; --accent: #5aa9ff; }} }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 1.7em; margin: 0 0 .3em; }} h2 {{ margin-top: 1.8em; }}
a {{ color: var(--accent); }} code {{ background: var(--card); padding: .1em .35em; border-radius: 4px; font-size: .92em; word-break: break-all; }}
.muted {{ color: var(--muted); }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ text-align: left; padding: .45em .6em; border-bottom: 1px solid var(--line); vertical-align: top; }}
.scroll {{ overflow-x: auto; }}
.langs a {{ display: inline-block; margin: 0 .5em .4em 0; }}
.row {{ display: grid; gap: 12px; margin: 12px 0; }} .row.two {{ grid-template-columns: 1fr 1fr; }}
@media (max-width: 700px) {{ .row.two {{ grid-template-columns: 1fr; }} }}
.fact {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; overflow-wrap: anywhere; }}
.fact h3 {{ margin: 0 0 .3em; font-size: 1em; }} .fact p {{ margin: 0; }}
.missing {{ color: #c0392b; font-weight: 600; }}
.meta {{ margin-top: .5em !important; font-size: .85em; color: var(--muted); }}
.tag {{ display: inline-block; padding: 0 .5em; border: 1px solid var(--line); border-radius: 999px; }}
</style>
</head>
<body><main>
{body}
</main></body>
</html>
"""


def help_page(langs, info):
    rows = "\n".join(
        f'<tr><td>{html.escape(LANGUAGE_NAMES[l])}</td><td><code>{l}</code></td>'
        f'<td><a href="../{l}/social.json">social</a> · <a href="../{l}/html.json">html</a> · '
        f'<a href="../{l}/markdown.json">markdown</a> · <a href="../{l}/plain.json">plain</a></td>'
        f'<td>{info["languages"][l]["translated"]} of {info["facts"]}</td>'
        f'<td><a href="../proofread/{l}/">proofread</a></td></tr>' for l in langs)
    body = f"""<h1>DigiByte DigiFacts</h1>
<p>Bite-size facts about DigiByte, for apps, websites and social media, in {len(langs)} languages. Free to use: the facts are MIT licensed.</p>

<h2>Get the DigiFacts</h2>
<p>Each language is a JSON file in four formats. The address is <code>https://digifacts.diginode.tools/&lt;language&gt;/&lt;format&gt;.json</code>, for example <a href="../en/social.json"><code>/en/social.json</code></a>.</p>
<ul>
<li><b>social</b> - links as short plain URLs, for social media: <code>Learn more: https://go.diginode.tools/7ttm</code></li>
<li><b>html</b> - links as HTML, for websites: <code>Learn more &lt;a href="https://go.diginode.tools/7ttm"&gt;here&lt;/a&gt;.</code></li>
<li><b>markdown</b> - links in Markdown: <code>Learn more [here](https://go.diginode.tools/7ttm).</code></li>
<li><b>plain</b> - no link, just the fact (e.g. for small displays). The link is still in <code>short_link</code>, and the full address in <code>url</code>.</li>
</ul>
<p>Each language only has the DigiFacts that are translated into it, so a translation is never mixed with English. When the English wording of a DigiFact changes, its translations are left out until they're updated. Every DigiFact keeps the same number in every language, so <b>DigiFact #12</b> is the same fact everywhere (some numbers are missing in languages that aren't fully translated yet).</p>
<div class="scroll"><table>
<tr><th>Language</th><th>Code</th><th>Files</th><th>Translated</th><th></th></tr>
{rows}
</table></div>

<h2>Other files</h2>
<ul>
<li><a href="../languages.json"><code>/languages.json</code></a> - the language codes, as a JSON list.</li>
<li><a href="../en/today.json"><code>/&lt;language&gt;/today.json</code></a> - the DigiFact of the day, changing at midnight UTC. Every fact is shown once before any repeats, and every fully translated language shows the same fact. Includes the title, number, and the text in all three formats.</li>
<li><a href="../en/feed.xml"><code>/&lt;language&gt;/feed.xml</code></a> - an RSS feed of the DigiFact of the day (the last 30 days). Use it with any RSS app, or an RSS bot to post DigiFacts to Discord, Telegram or social media.</li>
<li><a href="../info.json"><code>/info.json</code></a> - when the facts were last published, the block count used and where it came from, and each language's progress.</li>
</ul>

<h2>Using them</h2>
<ul>
<li>Show a random fact, e.g. when the page loads or once a minute.</li>
<li>Some facts include live data such as the number of DigiByte blocks, so fetch the file again every few hours. Don't fetch it more than once an hour.</li>
<li>Browsers can fetch the files directly (CORS is allowed), so they work in any website or app.</li>
</ul>

<h2>Add DigiFacts to your website</h2>
<p>Add this where you want a DigiFact to appear. It shows a random DigiFact, which changes every minute, and uses your site's font and colours:</p>
<pre><code>&lt;div data-digifacts data-lang="en"&gt;&lt;/div&gt;
&lt;script src="https://digifacts.diginode.tools/embed/v1/digifacts.js" async&gt;&lt;/script&gt;</code></pre>
<p>Options (attributes on the div): <code>data-lang</code> (a language code, or <code>auto</code> for the visitor's language), <code>data-box="no"</code> (text only), <code>data-interval</code> (seconds between DigiFacts, or <code>0</code> for just one), <code>data-credit="no"</code> (hide the small "About DigiByte DigiFacts" link), <code>data-accent</code> (a colour, e.g. <code>#0066cc</code>), and <code>data-exclude-tags</code> and <code>data-exclude</code> to hide DigiFacts (see <a href="#hiding">below</a>). Here it is:</p>
<div data-digifacts data-lang="en"></div>
<script src="../embed/v1/digifacts.js" async></script>
<p>On WordPress, you can use the <a href="https://github.com/DigiNode-Tools/digibyte-digifacts/tree/main/wordpress">DigiFacts plugin</a> instead.</p>

<h2 id="hiding">Hiding DigiFacts</h2>
<p>Some DigiFacts are about a particular website or project. A website that's mentioned in DigiFacts will usually want to hide those DigiFacts on its own site - its visitors are already there. That's what hiding is for: DigiFacts about your own site or project.</p>
<p>DigiFacts have <b>tags</b> for their topic, so the easiest way is to hide a tag. That also hides any DigiFacts given the tag in future:</p>
<pre><code>&lt;div data-digifacts data-exclude-tags="your-project"&gt;&lt;/div&gt;</code></pre>
<p>Each DigiFact's tags are shown next to it on the <a href="../proofread/en/">proofreading pages</a> - find the DigiFacts about your project to see its tag. If there isn't a tag for your project yet, <a href="{REPO_URL}/issues/new">ask for one</a>. You can also hide a single DigiFact by its <b>ID</b>, like <code>digifact-7ttm</code>, which never changes (unlike its number, which can change when DigiFacts are removed): <code>data-exclude="digifact-7ttm"</code>. The IDs are shown on the proofreading pages too, and every DigiFact in the JSON files has an <code>id</code> and <code>tags</code>. The WordPress plugin has the same options in its settings.</p>

<h2>How they're made</h2>
<p>The facts live in the <a href="{REPO_URL}">digibyte-digifacts</a> repository. Every hour, and whenever the facts change, a public <a href="{REPO_URL}/actions">GitHub Action</a> checks them, fills in the live data and publishes this site. The block count comes from several block explorers (currently {html.escape(", ".join(EXPLORERS))}); the middle value is used, and if none of them answer, an estimate based on DigiByte's 15 second block time.</p>
<p>Links in DigiFacts are short links, like <code>https://go.diginode.tools/7ttm</code>, so they fit in posts and on small displays. Clicks on them are counted with <a href="https://www.goatcounter.com">GoatCounter</a>, with no cookies and no personal data, to see which DigiFacts people find most interesting{' - see the <a href="../stats/">click stats</a>' if info.get("click_stats") else ""}.</p>

<h2>Help improve them</h2>
<p>Spotted a mistake, or a fact that's out of date? Translations can always be improved too, and new languages are welcome. See <a href="{REPO_URL}#contributing">how to contribute</a>, or <a href="../proofread/en/">read through the facts</a>.</p>
<p>DigiFacts are maintained by <a href="https://diginode.tools">DigiNode Tools</a>. If you find them useful, please consider <a href="{SPONSOR_URL}">sponsoring DigiNode Tools</a>.</p>
<p class="muted">Last published {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(info["built"]))}.</p>"""
    meta = preview_tags("DigiFacts", "Bite-size facts about DigiByte, for apps, websites and social media - in "
                        f"{len(langs)} languages, free to use.", CARDS[0], SITE_URL + "/")
    return PAGE.format(lang="en", title="DigiByte DigiFacts", body=body, meta=meta)


def suggest_url(key, number, text):
    """A link to the 'Suggest a correction' form, with the DigiFact filled in."""
    q = urllib.parse.urlencode({"template": "correction.yml", "title": f"Correction: DigiFact #{number} (ID {key})",
                                "fact": f"#{number} (ID {key})", "current": text})
    return f"{REPO_URL}/issues/new?{q}"


def proofread_page(lang, langs, en_facts, loc, count, fact_tags, stats, status, all_facts):
    links = " ".join(f'<a href="../{l}/">{html.escape(LANGUAGE_NAMES[l])}</a>' for l in langs)
    numbers = {key: n for n, key in enumerate(en_facts, start=1)}

    def details(key):
        tags = "".join(f' <span class="tag">{html.escape(t)}</span>' for t in fact_tags.get(key, []))
        s = (stats or {}).get("facts", {}).get(key)
        clicks = f' · <a href="../../stats/">{s["clicks"]:,} click{"" if s["clicks"] == 1 else "s"}</a>' if s else ""
        return f'<p class="meta">ID <code>{key}</code>{tags}{clicks}</p>'

    def card(key, fact, missing=False, english=False, outdated=None):
        if missing:
            return (f'<div class="fact"><h3>{html.escape(fill(fact["title"], count))}</h3><p class="missing">Not '
                    f'translated yet, so it isn\'t shown in {html.escape(LANGUAGE_NAMES[lang])}. '
                    f'<a href="{WEBLATE_URL}">Translate it on Weblate</a></p></div>')
        if outdated is not None:
            return (f'<div class="fact"><h3>{html.escape(fill(fact["title"], count))}</h3>'
                    f'<p class="muted">{html.escape(fill(outdated, count))}</p><p class="missing">The English has '
                    f'changed since this was translated, so it isn\'t shown until the translation is updated. '
                    f'<a href="{WEBLATE_URL}">Update it on Weblate</a></p></div>')
        text = fill(fact["content"], count) + fill(fact.get("link_social", ""), count)
        action = (f'<a href="{html.escape(suggest_url(key, numbers[key], text))}">Suggest a change</a>' if english else
                  f'<a href="{WEBLATE_URL}">Improve this translation</a>')
        return (f'<div class="fact"><h3>{html.escape(fill(fact["title"], count))}</h3>'
                f'<p>{html.escape(text)}</p>{details(key) if english else ""}<p class="meta">{action}</p></div>')

    rows = []
    chain = fallbacks(lang, all_facts)
    for key, en_fact in en_facts.items():
        if lang == "en":
            rows.append(f'<div class="row">{card(key, en_fact, english=True)}</div>')
            continue
        if status.get(key) == "translated":
            right = card(key, loc[key])
        elif status.get(key) == "outdated":
            old = next(all_facts[l][key]["content"] for l in chain if all_facts[l].get(key, {}).get("content"))
            right = card(key, en_fact, outdated=old)
        else:
            right = card(key, en_fact, missing=True)
        rows.append(f'<div class="row two">{card(key, en_fact, english=True)}{right}</div>')
    intro = ("Read through the English DigiFacts below." if lang == "en" else
             f"The English DigiFacts on the left, and the {html.escape(LANGUAGE_NAMES[lang])} translation on the right.")
    body = f"""<h1>DigiFacts proofreading: {html.escape(LANGUAGE_NAMES[lang])}</h1>
<p>{intro} Spotted a mistake, or a DigiFact that's out of date? Click <b>Suggest a change</b> under it. Translations are improved on <a href="{WEBLATE_URL}">Weblate</a>. Thank you!</p>
<p class="muted">Each DigiFact has an <b>ID</b>, like <code>digifact-7ttm</code>, that never changes (its number can, when DigiFacts are removed). Websites can use the IDs and tags to hide particular DigiFacts - see <a href="../../#hiding">hiding DigiFacts</a>.</p>
<p class="langs">{links}</p>
{"".join(rows)}
<p class="muted"><a href="../../">About DigiFacts</a></p>"""
    meta = preview_tags(f"DigiFacts proofreading: {LANGUAGE_NAMES[lang]}", "Every DigiFact, to read through and "
                        "suggest changes.", CARDS[0], f"{SITE_URL}/proofread/{lang}/")
    return PAGE.format(lang=lang, title=f"DigiFacts proofreading: {LANGUAGE_NAMES[lang]}", body=body, meta=meta)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: build/build.py OUT_DIR")
    out_dir = sys.argv[1]
    facts, titles = load_facts()
    langs = list(facts)
    tag_descriptions, fact_tags = load_tags(facts["en"])
    prev = previous_info()
    count, source, count_time, readings = block_count(prev)

    files, langs_info, localised, statuses = {}, {}, {}, {}
    day = int(time.time() // 86400)
    record = translations.update(translations.load_record(), facts)   # Which translations are current
    for lang in langs:
        loc, status = localise(facts, titles, lang, record)
        localised[lang], statuses[lang] = loc, status
        if not loc:   # No current translations yet: the language isn't published (apps use English instead)
            warn(f"{lang}: no current translations yet - not published")
            continue
        langs_info[lang] = {"name": LANGUAGE_NAMES[lang], "translated": len(loc),
                            "out_of_date": sum(1 for v in status.values() if v == "outdated")}
        for fmt, link_field in OUTPUT_FORMATS.items():
            data = {key: {"title": fill(f["title"], count),
                          "content": fill(f["content"] + (short_link(key, f, link_field) if link_field else ""), count),
                          "url": f.get("url", ""),
                          "short_url": short_url(key, f),
                          "short_link": SHORT_TEXT_BASE + key[len("digifact-"):] if f.get("url") else "",
                          "id": key,
                          "tags": fact_tags.get(key, [])} for key, f in loc.items()}
            files[f"{lang}/{fmt}.json"] = to_json(data)
        files[f"{lang}/today.json"], files[f"{lang}/feed.xml"] = today_and_feed(lang, loc, count, day, fact_tags)
    published = [l for l in langs if l in langs_info]
    files["languages.json"] = json.dumps(published) + "\n"
    with open(os.path.join(ROOT, "embed", "digifacts.js"), encoding="utf-8") as f:
        files["embed/v1/digifacts.js"] = f.read()   # The embed for any website (v1: keep it compatible)

    stats = click_stats([k for k, f in facts["en"].items() if f.get("url")], os.environ.get("DIGIFACTS_SITE_URL", "").rstrip("/"))
    if stats:
        files["stats.json"] = to_json(stats)

    # Did anything change since the last publish? (Not counting info.json's times)
    digest = hashlib.sha256("".join(f"{p}\n{c}" for p, c in sorted(files.items())).encode("utf-8")).hexdigest()
    changed = digest != prev.get("content_hash") or os.environ.get("FORCE_PUBLISH") == "1"
    if not changed:   # Keep the published block count, so info.json matches the published facts
        count, source, count_time = prev["block_count"], prev.get("block_count_source", source), prev["block_count_time"]

    info = {
        "built": int(time.time()),
        "facts": len(facts["en"]),
        "block_count": count,
        "block_count_source": source,
        "block_count_time": count_time,
        "explorers": readings,
        "languages": langs_info,
        "formats": list(OUTPUT_FORMATS),
        "tags": {t: {"description": d, "facts": sorted(k for k, v in fact_tags.items() if t in v)}
                 for t, d in tag_descriptions.items()},
        "source": REPO_URL,
        "commit": os.environ.get("GITHUB_SHA", ""),
        "click_stats": SITE_URL + "/stats/" if stats else "",
        "content_hash": digest,
    }
    files["info.json"] = to_json(info)
    # The help page is the home page (since 2026-10-25). DigiNode Tools older than v26.10.05 read DigiFacts from the
    # home page ('/?lang=en&format=social'): they keep their saved DigiFacts (with an error) until they update.
    files["index.html"] = re.sub(r'(href|src)="\.\./', r'\1="', help_page(published, info))
    files["help/index.html"] = ('<!doctype html><meta charset="utf-8"><title>DigiByte DigiFacts</title>'
                                f'<link rel="canonical" href="{SITE_URL}/"><meta http-equiv="refresh" content="0; url=../">'
                                '<a href="../">DigiByte DigiFacts</a>\n')   # The old address of the help page
    for lang in langs:   # Every language, published or not - translators need to see what's missing
        files[f"proofread/{lang}/index.html"] = proofread_page(lang, langs, localised["en"], localised[lang], count,
                                                               fact_tags, stats, statuses[lang], facts)
    files["proofread/index.html"] = '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=en/"><a href="en/">Proofread the DigiFacts</a>\n'
    files[".nojekyll"] = ""
    if stats:
        files["stats/index.html"] = stats_page(stats, localised["en"], count)
    short_links = {}
    for key, f in facts["en"].items():
        if f.get("url"):
            code = key[len("digifact-"):]
            text = f["content"] if len(f["content"]) <= 60 else f["content"][:60].rsplit(" ", 1)[0] + "..."
            title = fill(localised["en"][key]["title"], count) + ": " + fill(text, count)
            number, full = list(facts["en"]).index(key) + 1, fill(f["content"], count)
            short_links[code] = {"id": key, "url": f["url"],
                                 "page": redirect_page(f["url"], key, title, False, number, full),
                                 "qr_page": redirect_page(f["url"], key, title, True, number, full)}
            files[f"L/{code.upper()}.html"] = short_links[code]["qr_page"]   # This site's short links (before go)
            files[f"l/{code}.html"] = short_links[code]["page"]
    files["short-links.json"] = to_json(short_links)   # For go.diginode.tools

    for path, content in files.items():
        write(os.path.join(out_dir, path), content)
    for card in CARDS:   # Images: copied as they are
        os.makedirs(os.path.join(out_dir, os.path.dirname(card)), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, card), os.path.join(out_dir, card))

    print(f"Built {len(files)} files: {len(facts['en'])} facts in {len(published)} languages "
          f"({', '.join(l + ' ' + str(langs_info[l]['translated']) for l in published if l != 'en')}), "
          f"block count {count:,} ({source}){'' if changed else ' - nothing changed'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
