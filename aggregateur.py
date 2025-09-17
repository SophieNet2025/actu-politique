import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
import feedparser, yaml
from langdetect import detect
from googletrans import Translator
translator = Translator()

ROOT = Path(__file__).parent
OUT = ROOT / "feed.json"
SRC = ROOT / "sources.yaml"

def to_iso(dt_struct):
    if not dt_struct:
        return None
    dt = datetime(*dt_struct[:6], tzinfo=timezone.utc)
    return dt.isoformat()

def normalize_entry(entry, feed_title, feed_link):
    url = entry.get("link") or entry.get("id") or ""
    title = (entry.get("title") or "").strip()
    if "content" in entry and entry.content:
        content_html = entry.content[0].value
    else:
        content_html = entry.get("summary", "") or ""
        # Détection et traduction automatique (coller ce bloc entre 25 et 26)
    try:
        to_detect = (content_html or title)[:4000]  # on prend un échantillon
        lang = detect(to_detect)
    except Exception:
        lang = "unknown"

    # Si ce n’est ni du français ni de l’anglais, on traduit en français
    if lang not in ("fr", "en") and (content_html or title):
        try:
            if content_html:
                content_html = translator.translate(content_html, dest="fr").text
            if title:
                title = translator.translate(title, dest="fr").text
            lang = "fr"
        except Exception as e:
            print("Traduction impossible pour un item:", e)
    
    dt = entry.get("published_parsed") or entry.get("updated_parsed")
    date_iso = to_iso(dt) or datetime.now(timezone.utc).isoformat()
    authors = [{"name": entry.get("author")}] if entry.get("author") else []
    tags = [t.get("term") for t in entry.get("tags", []) if t.get("term")]
    h = hashlib.sha256((url or title).encode("utf-8")).hexdigest()
return {
    "id": h,
    "url": url,
    "title": title,
    "content_html": content_html,  # on garde le texte tel quel, FR ou EN
    "date_published": date_iso,
    "authors": authors,
    "tags": tags,
    "source": { "name": feed_title, "url": feed_link },
    "lang": lang
}

def load_sources():
    with open(SRC, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["feeds"]

def fetch_feed(url):
    try:
        parsed = feedparser.parse(url)
        # feedparser signale les anomalies via "bozo"
        if getattr(parsed, "bozo", False) and hasattr(parsed, "bozo_exception"):
            print(f"[WARN] Problème sur {url}: {parsed.bozo_exception}")
        return parsed
    except Exception as e:
        # Si une source échoue, on log et on renvoie un "flux vide" pour continuer
        print(f"[ERROR] Impossible de récupérer {url}: {e}")
        class Empty: 
            pass
        empty = Empty()
        empty.feed = {"title": url, "link": url}
        empty.entries = []
        return empty

def build_feed(public_feed_url=""):
    feeds = load_sources()
    items, seen = [], set()
    for f in feeds:
        parsed = fetch_feed(f["url"])
        feed_title = parsed.feed.get("title", f.get("name",""))
        feed_link = parsed.feed.get("link", f["url"])
        for e in parsed.entries:
            item = normalize_entry(e, feed_title, feed_link)
            key = e.get("link") or e.get("id") or item["id"]
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    # tri du plus récent au plus ancien
    def key_dt(it):
        try:
            return datetime.fromisoformat(it["date_published"])
        except Exception:
            return datetime.now(timezone.utc)
    items.sort(key=key_dt, reverse=True)
    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Actu – Politique internationale (agrégée)",
        "home_page_url": "https://example.org",
        "feed_url": public_feed_url or "https://tonpseudo.github.io/actu-politique/feed.json",
        "items": items
    }

if __name__ == "__main__":
    feed = build_feed()
    OUT.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK -> {OUT}")
