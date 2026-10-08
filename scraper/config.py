from pathlib import Path

USER_AGENT = "OW-SLM-UE/0.1 (student research; albalatnathan.etu@gmail.com)"

FANDOM_API = "https://overwatch.fandom.com/api.php"
FANDOM_BASE = "https://overwatch.fandom.com/wiki/"
FANDOM_DELAY = 1.0

LIQUI_API = "https://liquipedia.net/overwatch/api.php"
LIQUI_BASE = "https://liquipedia.net/overwatch/"
LIQUI_DELAY = 2.1

LICENSE = "CC-BY-SA 3.0"
MIN_WORDS = 50

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
