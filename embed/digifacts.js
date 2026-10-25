/*!
 * DigiByte DigiFacts embed - show a random DigiFact on any website. It changes every minute.
 * https://github.com/DigiNode-Tools/digibyte-digifacts  (MIT licence)
 *
 * Add this where you want the DigiFact:
 *   <div data-digifacts></div>
 *   <script src="https://digifacts.diginode.tools/embed/v1/digifacts.js" async></script>
 *
 * Options (as attributes on the div):
 *   data-lang="de"         Language code (default: en). "auto" uses the visitor's browser language, if available.
 *   data-box="no"          No box - just the text (default: a box)
 *   data-interval="120"    Seconds between DigiFacts (default: 60, minimum 10). "0" shows one DigiFact only.
 *   data-credit="no"       Hide the small "About DigiByte DigiFacts" link
 *   data-accent="#0066cc"  The colour of the box border and links
 *   data-exclude-tags="your-project"    Hide DigiFacts with these tags (comma separated) - for DigiFacts about your own
 *                                       site or project
 *   data-exclude="digifact-7ttm"        Hide these DigiFacts by ID (comma separated). IDs never change.
 *
 * The DigiFact is drawn in its own shadow DOM, so your site's styles can't break it (and it can't affect your site).
 * It uses your site's font and text colour. Nothing is shown if the DigiFacts can't be loaded.
 */
(function () {
  "use strict";

  var SITE = "https://digifacts.diginode.tools";
  var MIN_INTERVAL = 10;

  var CSS =
    ":host{display:block}" +
    ".d{--a:#0066cc;margin:1em 0;font:inherit;color:inherit;line-height:1.5}" +
    ".d.box{padding:.8em 1em;border-radius:8px;border:1px solid rgba(0,102,204,.35);" +
    "border-color:color-mix(in srgb,var(--a) 35%,transparent)}" +
    ".t{margin:0 0 .3em;font-weight:700}p{margin:0}" +
    "a{color:var(--a);text-underline-offset:2px}a:hover,a:focus{opacity:.7}" +
    ".c{margin-top:.5em;font-size:.65em;opacity:.65}.c a{color:inherit}";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  // The content is the html format: text plus at most one <a href="https://...">. Rebuild it from scratch, keeping
  // only text and https links, so nothing else from the data can ever reach the page.
  function content(html) {
    var p = el("p");
    var doc = new DOMParser().parseFromString("<body>" + html + "</body>", "text/html");
    var nodes = doc.body.childNodes;
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      if (n.nodeType === 3) {
        p.appendChild(document.createTextNode(n.textContent));
      } else if (n.nodeType === 1 && n.tagName === "A" && /^https:\/\//.test(n.getAttribute("href") || "")) {
        var a = el("a", "", n.textContent);
        a.href = n.getAttribute("href");
        a.target = "_blank";
        a.rel = "noopener";
        p.appendChild(a);
      } else if (n.nodeType === 1) {
        p.appendChild(document.createTextNode(n.textContent));
      }
    }
    return p;
  }

  function language(host, available) {
    var lang = (host.getAttribute("data-lang") || "en").toLowerCase();
    if (lang === "auto") {
      var nav = (navigator.languages && navigator.languages[0]) || navigator.language || "en";
      lang = nav.toLowerCase();
      if (available.indexOf(lang) < 0) lang = lang.split("-")[0];
    }
    return available.indexOf(lang) >= 0 ? lang : "en";
  }

  var cache = {};
  function load(lang) {
    if (!cache[lang]) {
      cache[lang] = fetch(SITE + "/" + lang + "/html.json")
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          var list = [];
          for (var k in d) {
            if (d[k] && d[k].title && d[k].content) {
              list.push({ title: d[k].title, content: d[k].content, id: d[k].id || k, tags: d[k].tags || [] });
            }
          }
          return list;
        });
    }
    return cache[lang];
  }

  // A comma-separated attribute as a list
  function attrList(host, name) {
    return (host.getAttribute(name) || "").split(",").map(function (s) { return s.trim().toLowerCase(); })
      .filter(function (s) { return s; });
  }

  // The DigiFacts this site wants: without the hidden IDs and tags. The hidden ones are listed in the browser console.
  function wanted(host, facts) {
    var ids = attrList(host, "data-exclude"), tags = attrList(host, "data-exclude-tags"), hidden = [];
    var shown = facts.filter(function (f) {
      var why = [];
      var id = String(f.id).toLowerCase();
      if (ids.indexOf(id) >= 0 || ids.indexOf(id.replace(/^digifact-/, "")) >= 0) why.push("ID");
      for (var i = 0; i < f.tags.length; i++) if (tags.indexOf(f.tags[i]) >= 0) why.push("topic " + f.tags[i]);
      if (why.length) {
        var text = content(f.content).textContent;
        hidden.push(f.title + " " + f.id + " (" + why.join(", ") + "): " + (text.length > 80 ? text.slice(0, 80) + "..." : text));
      }
      return !why.length;
    });
    if (hidden.length && window.console) {
      console.info("DigiFacts: this site hides " + hidden.length + " of " + facts.length + " DigiFacts\n" + hidden.join("\n"));
    }
    return shown;
  }

  function show(host, facts) {
    facts = wanted(host, facts);
    if (!facts.length) return;
    var root = host.shadowRoot || host.attachShadow({ mode: "open" });
    var box = el("div", "d" + (host.getAttribute("data-box") === "no" ? "" : " box"));
    var accent = host.getAttribute("data-accent");
    if (accent && /^#[0-9a-fA-F]{3,8}$/.test(accent)) box.style.setProperty("--a", accent);

    var title = el("p", "t");
    var body = el("div");
    box.appendChild(title);
    box.appendChild(body);
    if (host.getAttribute("data-credit") !== "no") {
      var credit = el("p", "c");
      var link = el("a", "", "About DigiByte DigiFacts");
      link.href = SITE + "/";
      link.target = "_blank";
      link.rel = "noopener";
      credit.appendChild(link);
      box.appendChild(credit);
    }
    root.innerHTML = "";
    var style = el("style");
    style.textContent = CSS;
    root.appendChild(style);
    root.appendChild(box);

    var last = -1;
    function next() {
      var i;
      do { i = Math.floor(Math.random() * facts.length); } while (facts.length > 1 && i === last);
      last = i;
      title.textContent = facts[i].title;
      body.innerHTML = "";
      body.appendChild(content(facts[i].content));
    }
    next();

    var seconds = parseInt(host.getAttribute("data-interval") || "60", 10);
    if (seconds > 0 && facts.length > 1) {
      setInterval(function () { if (!document.hidden) next(); }, Math.max(seconds, MIN_INTERVAL) * 1000);
    }
  }

  function start() {
    var hosts = document.querySelectorAll("[data-digifacts]");
    if (!hosts.length || !window.fetch || !window.DOMParser || !document.body.attachShadow) return;
    fetch(SITE + "/languages.json")
      .then(function (r) { return r.ok ? r.json() : ["en"]; })
      .catch(function () { return ["en"]; })
      .then(function (available) {
        for (var i = 0; i < hosts.length; i++) {
          if (hosts[i].hasAttribute("data-digifacts-started")) continue;
          hosts[i].setAttribute("data-digifacts-started", "");
          (function (host) {
            load(language(host, available))
              .then(function (facts) { show(host, facts); })
              .catch(function () { /* Show nothing if the DigiFacts can't be loaded */ });
          })(hosts[i]);
        }
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
