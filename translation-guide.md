# Translating DigiFacts

Thank you for helping! Translations make DigiByte easier to learn about for people around the world.

**The easiest way to translate is on [Weblate](https://hosted.weblate.org/projects/digibyte-digifacts/)**: sign in, choose a language (or add a new one), and translate in your browser. Weblate shows you the English next to each string, warns you if a live value like `$blocks_tot_mil` goes missing, and sends your translations here as a pull request. The rest of this guide is for editing the files directly.

## How the files work

Each language has its own file in [`facts/`](facts/), named with its two-letter language code (e.g. `facts/de.json` for German). [`facts/en.json`](facts/en.json) is the original that every translation is based on, and every file uses the same keys. Each key is the DigiFact's ID (e.g. `digifact-7ttm`) - leave the keys as they are:

```json
"_title": "DigiFact #{number}",
"digifact-7ttm": {
  "content": "DigiByte has upgraded the network a number of times...",
  "url": "https://github.com/DigiByte-Core/digibyte/wiki/Historic-Timeline",
  "link_social": " Learn more: https://github.com/DigiByte-Core/digibyte/wiki/Historic-Timeline",
  "link_html": " Learn more <a target=\"_blank\" href=\"https://github.com/DigiByte-Core/digibyte/wiki/Historic-Timeline\">here</a>.",
  "link_md": " Learn more [here](https://github.com/DigiByte-Core/digibyte/wiki/Historic-Timeline)."
}
```

- Translate the `_title` at the top of the file once. It's used as the title of every fact, and `{number}` is replaced by the fact's number - keep `{number}` exactly as it is.
- Translate each fact's `content`, and the words in `link_social`, `link_html` and `link_md`.
- Keep the `url` as it is, and keep the same link in all three link fields. Each link field starts with a space.
- Keep live values such as `$blocks_tot_mil` exactly as they are - they're replaced with live data (e.g. 24.3). Move them to wherever they belong in your sentence.
- `link_html` may only contain the one link, written exactly as above. Nothing else may contain `<` or `>`.

Only translated facts are shown in your language - a fact that isn't translated yet is simply left out (it's never shown in English instead), so it's fine to translate a few facts at a time. When the English wording of a fact changes, its translations are left out until they're updated: Weblate marks them **Needs editing**. Update the translation (even a small change counts) and it's shown again.

## Improving a translation

1. Read through the language side by side with English on the [proofreading pages](https://digifacts.diginode.tools/proofread/).
2. Edit `facts/<code>.json` on GitHub (open the file and click the pencil icon). GitHub will make a copy of the repository for you.
3. Propose the change and open a pull request. Please say what you changed and why.

Not comfortable editing JSON? [Open an issue](https://github.com/DigiNode-Tools/digibyte-digifacts/issues) with the fact number and your corrected text.

## Adding a new language

1. Copy `facts/en.json` to `facts/<code>.json`, using the language's two-letter [ISO 639-1 code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes).
2. Translate it (see above). You can translate some facts and leave the rest in English for now.
3. Open a pull request. Add the language's name to `LANGUAGE_NAMES` in [`build/build.py`](build/build.py), or say in the pull request and it will be added for you.

Machine translation (e.g. DeepL or an AI assistant) is a fine starting point, but please have the result checked by a native speaker - mention in the pull request if it hasn't been.

## Checking your changes

When you open a pull request, the files are checked automatically, and any mistakes are shown on the pull request. To check them yourself first, run `python3 build/build.py /tmp/digifacts` - it reports any mistakes and builds the website into that folder.
