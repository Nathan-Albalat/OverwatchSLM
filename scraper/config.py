from pathlib import Path

USER_AGENT = "OW-SLM-UE/0.1 (student research; albalatnathan.etu@gmail.com)"

FANDOM_API = "https://overwatch.fandom.com/api.php"
FANDOM_BASE = "https://overwatch.fandom.com/wiki/"
FANDOM_DELAY = 1.0

LIQUI_API = "https://liquipedia.net/overwatch/api.php"
LIQUI_BASE = "https://liquipedia.net/overwatch/"
LIQUI_DELAY = 2.1

# Notes de patch officielles (texte Blizzard, pas CC-BY-SA : citer la source, usage de recherche).
# Ajoutees car les wikis publient les pages de patch avec 2-4 semaines de retard (Liquipedia par lots).
BLIZZARD_PATCH_NOTES = "https://overwatch.blizzard.com/en-us/news/patch-notes/live/{month}/"
BLIZZARD_LICENSE = "(c) Blizzard Entertainment - official patch notes"

SOURCES = ("fandom", "liquipedia", "blizzard")

LICENSE = "CC-BY-SA 3.0"
MIN_WORDS = 50

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
