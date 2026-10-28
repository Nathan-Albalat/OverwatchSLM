"""Prompts du banc. Le format RAG est partage avec le futur constructeur d'exemples RAFT :
l'entrainement et l'evaluation doivent voir exactement la meme chose."""
from gen.build_dataset import SYSTEM_PROMPT  # noqa: F401  (meme prompt systeme que l'entrainement)

RAG_HEADER = "Use the following passages to answer. If they do not contain the answer, say you do not know."
# Variante « recent » (option de config `rag_header = "recent"`) : le corpus garde toutes les versions passees
# (historiques d'equilibrage, anciens patchs) ; on demande de retenir la plus recente en cas de desaccord.
RAG_HEADERS = {
    "default": RAG_HEADER,
    "recent": "Use the following passages to answer. They may describe older versions of the game: if they disagree, "
              "give the most recent information (latest patch). If they do not contain the answer, say you do not know.",
}


def format_user_prompt(question, passages=None, header="default"):
    """passages : liste de str (ou de dicts avec 'text'). Sans passages : la question seule."""
    if not passages:
        return question
    blocks = []
    for i, p in enumerate(passages, 1):
        text = p["text"] if isinstance(p, dict) else p
        blocks.append(f"[{i}] {text.strip()}")
    return f"{RAG_HEADERS[header]}\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"


def build_messages(question, passages=None, header="default"):
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": format_user_prompt(question, passages, header)}]
