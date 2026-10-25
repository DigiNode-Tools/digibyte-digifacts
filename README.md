# DigiByte DigiFacts

<!-- sponsors:short -->
<a href="https://github.com/sponsors/DigiNode-Tools"><img src="https://img.shields.io/badge/Sponsor%20on-GitHub-0066CC?style=for-the-badge&labelColor=002352&logo=githubsponsors&logoColor=EA4AAA" alt="Sponsor DigiNode Tools on GitHub"></a> <a href="https://ko-fi.com/diginode"><img src="https://img.shields.io/badge/Support%20on-Ko--fi-0066CC?style=for-the-badge&labelColor=002352&logo=kofi&logoColor=FF5E5B" alt="Support DigiNode Tools on Ko-fi"></a>

**Find this useful?** Please consider sponsoring me on [GitHub](https://github.com/sponsors/DigiNode-Tools) or [Ko-fi](https://ko-fi.com/diginode), so I can devote more time to DigiNode Tools and projects like this one.
<!-- /sponsors:short -->

Bite-size facts about DigiByte, for apps, websites and social media. Available in 12 languages, with live data from the DigiByte blockchain.

**Website:** https://digifacts.diginode.tools/

## About DigiFacts

DigiFacts are short facts about DigiByte, designed to be shown in apps and websites and shared on social media, to help people learn about DigiByte.

The original DigiFacts were written by members of the DigiByte community in 2021 ([DigiByte-Core/DigiFacts](https://github.com/DigiByte-Core/DigiFacts)). These DigiFacts are based on them, but have been significantly revised and expanded, translated, and given live data such as the number of DigiByte blocks.

## Using DigiFacts

Each language is a JSON file in four formats:

```
https://digifacts.diginode.tools/<language>/<format>.json
```

For example: https://digifacts.diginode.tools/en/social.json

| Format | Links look like | Best for |
|---|---|---|
| `social` | `Learn more: https://go.diginode.tools/7ttm` | Social media, apps, terminals |
| `html` | `Learn more <a href="https://go.diginode.tools/7ttm">here</a>.` | Websites |
| `markdown` | `Learn more [here](https://go.diginode.tools/7ttm).` | Markdown |
| `plain` | No link - just the fact (the link is still in `short_link`) | Small displays, speech |

The English files have every fact, in order; each other language has only the facts translated into it (a fact without a current translation is left out, never shown in English), with the same numbers as English. Each fact has a `title` (which includes its number, e.g. "DigiFact #1"), `content`, `url` (the full address) and, for a fact with a link, `short_link` (e.g. `https://go.diginode.tools/7ttm`) and `short_url` (the same in capitals, for QR codes: they're smaller that way). The keys are each fact's ID (e.g. `digifact-7ttm`), which never changes - use the order of the file, or the number in the title, for the fact's number. Each fact also has its `id` and `tags`. A fact that isn't translated yet is included in English.

Languages: `en` English, `de` German, `es` Spanish, `fr` French, `hi` Hindi, `it` Italian, `ja` Japanese, `ko` Korean, `nl` Dutch, `pt` Portuguese, `ru` Russian, `zh` Chinese (Simplified). The list is also at https://digifacts.diginode.tools/languages.json, and https://digifacts.diginode.tools/info.json shows each language's progress, the block count used and when the facts were last published.

- **DigiFact of the day:** https://digifacts.diginode.tools/en/today.json is the same fact for everyone, in every language, changing at midnight UTC (every fact is shown once before any repeats). It has the `date`, `number`, `title`, `url`, and the text as `text` (social format), `html`, `markdown` and `plain`.
- **RSS feed:** https://digifacts.diginode.tools/en/feed.xml has the DigiFact of the day for the last 30 days - use it with any RSS app, or an RSS bot to post DigiFacts to Discord, Telegram or social media.
- Show a random fact, e.g. when the page loads or once a minute.
- Some facts include live data, so fetch the file again every few hours - but not more than once an hour.
- Browsers can fetch the files directly (CORS is allowed).

## Add DigiFacts to your website

Add this where you want a DigiFact to appear. It shows a random DigiFact, which changes every minute, and uses your site's font and colours:

```html
<div data-digifacts data-lang="en"></div>
<script src="https://digifacts.diginode.tools/embed/v1/digifacts.js" async></script>
```

Options (attributes on the div):

| Option | What it does |
|---|---|
| `data-lang="de"` | The language (default `en`). `auto` uses the visitor's browser language, if available. |
| `data-box="no"` | Just the text, without a box. |
| `data-interval="120"` | Seconds between DigiFacts (default 60, minimum 10). `0` shows one DigiFact only. |
| `data-credit="no"` | Hide the small "About DigiByte DigiFacts" link. |
| `data-accent="#0066cc"` | The colour of the box border and links. |
| `data-exclude-tags="your-project"` | Hide DigiFacts with these tags (comma separated) - for DigiFacts about your own site or project. |
| `data-exclude="digifact-7ttm"` | Hide these DigiFacts, by ID (comma separated). IDs never change. |

The DigiFact is drawn in its own shadow DOM, so your site's styles can't affect it and it can't affect your site. It fetches only the DigiFacts files above, and shows nothing if they can't be loaded. The `v1` in the address means it won't change in a way that could break your page. The code is in [`embed/`](embed/).

### On WordPress

Use the [DigiFacts WordPress plugin](wordpress/) - download `digibyte-digifacts.zip` from the [releases](https://github.com/DigiNode-Tools/digibyte-digifacts/releases), then add the `[digifacts]` shortcode or the DigiByte DigiFacts block. It works with page caching, and your visitors' browsers don't contact any other site.

## On a Tronbyt display

The DigiFacts app for [Tronbyt](https://github.com/tronbyt) shows a DigiFact on your Tronbyt (or Tidbyt) display. It opens with the DigiByte logo and the DigiFact's number, then the DigiFact scrolls up the display, ending with a QR code if it has a link. Choose from 8 languages, three text sizes, and the DigiFact of the day or a random one. It works on 64x32, 64x64 and 128x64 displays.

![The DigiFacts app on a 128x64 Tronbyt display](images/tronbyt-digifacts.webp)

Install it from the Tronbyt app store on your Tronbyt server, or see it in the [Tronbyt App Viewer](https://tronbyt.github.io/apps/details/digibyte-digifacts.html). The app's source is in the [Tronbyt apps repository](https://github.com/tronbyt/apps/tree/main/apps/digibyte-digifacts).

## How DigiFacts are built

Everything is in this repository, so anyone can see exactly how DigiFacts are made:

- The facts are in [`facts/`](facts/), one file per language. [`facts/en.json`](facts/en.json) is the original that the translations are based on.
- A [GitHub Action](.github/workflows/build.yml) runs [`build/build.py`](build/build.py) every hour and whenever the facts change. It checks every file, fills in the live data, and publishes the website on GitHub Pages. If a file has a mistake, nothing is published and the previous version stays live.
- The block count comes from several block explorers (chainz.cryptoid.info, digibyte.io and Atomic Wallet's explorer). The middle value is used, readings that look wrong are ignored, and the count never goes backwards. If no explorer answers, it's estimated from DigiByte's 15 second block time.
- Every run is public on the [Actions tab](https://github.com/DigiNode-Tools/digibyte-digifacts/actions).

## Contributing

Corrections, new DigiFacts and translations are all welcome - you don't need to know Git or JSON.

- **Suggest a new DigiFact:** fill in the [new DigiFact form](https://github.com/DigiNode-Tools/digibyte-digifacts/issues/new?template=new-digifact.yml).
- **Fix a mistake, or report one that's out of date:** use the **Suggest a change** link under the DigiFact on the [proofreading pages](https://digifacts.diginode.tools/proofread/en/), which fills in the [correction form](https://github.com/DigiNode-Tools/digibyte-digifacts/issues/new?template=correction.yml) for you.
- **Translate:** on [Weblate](https://hosted.weblate.org/engage/digibyte-digifacts/) (see [Translating](#translating)).

You'll need a free GitHub account for the forms. Every suggestion is checked before it's added. New and corrected DigiFacts are written in English first, and translated from there.

### Editing the DigiFacts directly

If you're comfortable with pull requests, you can edit `facts/en.json` yourself:

- **Every DigiFact has an ID** - its key, e.g. `digifact-7ttm`: `digifact-` and four random letters and numbers. The ID never changes, even when the DigiFact's number does (DigiFacts are numbered by their order in `facts/en.json`). Websites use the IDs to hide particular DigiFacts, and translations are matched to DigiFacts by their ID.
- **Fixing a DigiFact:** edit its text and keep its ID. A correction must still be the same DigiFact - if it would say something different, add a new DigiFact instead. Pull requests are checked automatically for this.
- **Adding a DigiFact:** add it to `facts/en.json` wherever it belongs in the list, with any key, or none - for example `"new": { "content": "..." }`, or just `{ "content": "..." }`. It gets its ID automatically when it's merged. Never rename an existing DigiFact's ID. (IDs are random - with no vowels, so they can't spell words, and never two numbers in a row - so they can't be mistaken for DigiFact numbers.)
- **Removing a DigiFact:** delete it from `facts/en.json` only. The DigiFacts after it are renumbered, and it's removed from the translations and `tags.json` automatically.
- **Every DigiFact stands alone.** Apps show them one at a time, at random or one a day, so each must make sense on its own, read in any order: don't start with "Also" or "Another", and don't refer to other DigiFacts.
- Keep the wording neutral: no marketing, and nothing about price. A single DigiFact telling the community about a DigiByte project and what it does is fine.
- Include at most one link - the full address, not a shortened one (the build makes a short link for every DigiFact, and third-party shorteners aren't allowed: their links can expire). Put it in `url`, and in all three link fields (`link_social`, `link_html` and `link_md`) - see the existing DigiFacts for the format.

### Tags

[`tags.json`](tags.json) gives some DigiFacts a topic, by ID - for example, the DigiFacts about a particular project - so a website that's mentioned in DigiFacts can hide them on its own site (see [Hiding DigiFacts](https://digifacts.diginode.tools/#hiding)). If your project is mentioned and doesn't have a tag yet, open an issue to ask for one. To add a tag, describe it under `tags` and add it to the DigiFacts under `facts`.

### Translating

[![Translation status](https://hosted.weblate.org/widget/digibyte-digifacts/svg-badge.svg)](https://hosted.weblate.org/engage/digibyte-digifacts/)

DigiFacts are translated on [Weblate](https://hosted.weblate.org/projects/digibyte-digifacts/) - the easiest way to help. Sign in, choose a language, and translate or improve the DigiFacts in your browser - no GitHub or JSON needed. Your translations are sent here as pull requests. Thank you to Weblate for hosting libre projects for free.

You can also edit the files directly. Each language has its own file in `facts/`, with the same keys as `facts/en.json`. Translate the `_title` at the top of the file (once - it's used for every fact, with `{number}` replaced by the fact's number), then each fact's `content` and three link fields. Leave the `url` as it is. See the [translation guide](translation-guide.md).

### Live data

These can be used in a fact, and are replaced with live values when the website is published:

| Value | Example | Shows |
|---|---|---|
| `$blocks_tot_mil` | 24.3 | The number of DigiByte blocks in millions (rounded down to 0.1 million) |
| `$blocks_tot_cs` | 24,372,537 | The number of DigiByte blocks, with commas |
| `$blocks_tot` | 24372537 | The number of DigiByte blocks |

Write the value in the fact where the number should go. For example:

> DigiByte has over `$blocks_tot_mil` million blocks.

is published as "DigiByte has over 24.3 million blocks", and stays up to date. Translations should use the same values as the English fact.

Would another live value make a good DigiFact (e.g. something else from the DigiByte blockchain)? Suggest it in the [new DigiFact form](https://github.com/DigiNode-Tools/digibyte-digifacts/issues/new?template=new-digifact.yml), and say what it should show.

## Projects using DigiFacts

- [DigiNode Tools](https://diginode.tools) - on the DigiNode Tools website and in the DigiNode Dashboard.

## Disclaimer

DigiFacts are written by the DigiByte community, for the DigiByte community. Please help keep them current and accurate. Always do your own research before using any service or product mentioned in a DigiFact - mentions are not endorsements.

## Licence

The DigiFacts, the website build and the embed are MIT - see [LICENSE](LICENSE). Anyone can use DigiFacts, as long as the copyright notice is kept. The WordPress plugin is GPL-2.0-or-later - see [wordpress/LICENSE](wordpress/LICENSE). Based on the [original DigiFacts](https://github.com/DigiByte-Core/DigiFacts) by DigiByte Core (MIT).

DigiFacts are maintained by [DigiNode Tools](https://diginode.tools).
