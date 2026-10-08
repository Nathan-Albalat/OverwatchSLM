"""Prompts du banc. Le format RAG est partage avec le futur constructeur d'exemples RAFT :
l'entrainement et l'evaluation doivent voir exactement la meme chose."""
from gen.build_dataset import SYSTEM_PROMPT  # noqa: F401  (meme prompt systeme que l'entrainement)

RAG_HEADER = "Use the following passages to answer. If they do not contain the answer, say you do not know."


def format_user_prompt(question, passages=None):
    """passages : liste de str (ou de dicts avec 'text'). Sans passages : la question seule."""
    if not passages:
        return question
    blocks = []
    for i, p in enumerate(passages, 1):
        text = p["text"] if isinstance(p, dict) else p
        blocks.append(f"[{i}] {text.strip()}")
    return f"{RAG_HEADER}\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"


def build_messages(question, passages=None):
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": format_user_prompt(question, passages)}]
