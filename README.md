# SLM - Overwatch

Scraping et nettoyage des wikis Overwatch (Fandom et Liquipedia) pour un SLM fine-tune + RAG.

## Usage

```
uv sync
uv run ow-scrape fandom [--limit N]
uv run ow-scrape liquipedia [--limit N]
uv run ow-scrape clean
uv run ow-scrape stats
```

La collecte est reprenable : les pageid deja presents dans `data/raw/*/pages.jsonl` sont ignores.

## Attribution

- Overwatch Wiki (Fandom) : https://overwatch.fandom.com, CC-BY-SA 3.0.
- Liquipedia Overwatch : https://liquipedia.net/overwatch, CC-BY-SA 3.0.
  API : 1 requete / 2 s max, gzip, User-Agent avec contact.
