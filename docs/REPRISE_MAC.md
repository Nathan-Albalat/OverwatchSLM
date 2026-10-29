# Reprise du projet sur le Mac (et démo de soutenance)

Le projet a été développé sur le PC Windows (RTX 5070 Ti). Ce guide explique comment le récupérer sur le Mac,
faire tourner la démo, et ce qui peut ou non continuer côté Mac.

## 1. Côté PC : préparer le dossier partagé

```
# depuis la racine du dépôt, sur le PC (interpréteur uv + paquets du venv, voir CLAUDE.md)
python -m demo.bundle "<dossier partagé>/OverwatchSLM"
```

Le dossier obtenu est un projet prêt à l'emploi (~3,8 Go) :
- le **code** au dernier commit (`git archive HEAD`, sans l'historique git ; les modifications non commitées ne sont pas incluses, un avertissement le signale) ;
- l'**index RAG** : `data/rag/{docs.jsonl, bm25.pkl, emb.npy, emb_ids.json}` (~110 Mo) ;
- les **modèles fine-tunés** : `data/train/qwen3-4b-raft-v2/gguf/` (2,5 Go) et `data/train/qwen3-1.7b-raft/gguf/` (1,1 Go), chacun avec son `Modelfile` ;
- `BUNDLE_MANIFEST.json` : commit exporté, taille et sha256 de chaque fichier.

Options : `--runs qwen3-1.7b-raft` (un seul modèle), `--with-query-cache` (+225 Mo : embeddings des questions déjà posées, les
questions du test sont alors encodées instantanément), `--no-code` (données seulement, si le dépôt est déjà cloné côté Mac).

**Variante avec l'historique git** (recommandée pour continuer le projet) : pousser le dépôt depuis le PC (`git push`, il a des
commits locaux non poussés), puis sur le Mac `git clone git@github.com:Nathan-Albalat/OverwatchSLM.git` et utiliser le
bundle en `--no-code` : copier son dossier `data/` à la racine du clone.

## 2. Côté Mac : installation

1. **Ollama** : application macOS depuis ollama.com (elle lance le serveur sur `localhost:11434`).
2. **uv** : `brew install uv` (ou le script d'installation officiel d'uv).
3. Copier `<dossier partagé>/OverwatchSLM` en local (par exemple `~/Projets/OverwatchSLM`) : lire 4 Go de modèles
   depuis un dossier réseau ralentirait le chargement.
4. Dans le dossier du projet :
   ```
   uv sync                      # Python 3.12 et dépendances (pas de Smart App Control sur Mac : uv run marche directement)
   ollama pull qwen3-embedding:0.6b                                            # obligatoire pour la recherche RAG
   ollama create ow-qwen3-4b-raft-v2 -f data/train/qwen3-4b-raft-v2/gguf/Modelfile
   ollama create ow-qwen3-1.7b-raft  -f data/train/qwen3-1.7b-raft/gguf/Modelfile
   ollama pull hf.co/unsloth/Qwen3-4B-GGUF:Q4_K_M                             # modele par defaut de la demo (4B de base)
   ```
   Facultatif, pour comparer : `...Qwen3-1.7B-GGUF:Q4_K_M` et les RAFT ci-dessus.
5. Vérifier :
   ```
   uv run python -m rag.cli query "Roadhog Chain Hook cooldown" --k 4       # doit lister des passages, dont les notes du 6 oct. 2026
   uv run python -m demo.demo --ask "What is the ultimate ability of the hero Kestrel?"
   ```

## 3. La démo

```
uv run python -m demo.demo                              # Qwen3 4B de base + RAG, normalisation auto (défaut)
uv run python -m demo.demo --model ow-qwen3-4b-raft-v2  # le RAFT, pour comparer
uv run python -m demo.demo --model ow-qwen3-1.7b-raft   # le plus petit modèle
```

Commandes : `/compare` (la question suivante est posée sans RAG puis avec), `/rag` (active ou coupe le RAG),
`/sources` (affiche ou masque les passages trouvés), `/model NOM`, `/aide`, `/quitter`.
Chaque réponse affiche le temps total, le temps de recherche, le délai avant le premier mot, les tokens/s et la mémoire du modèle.
La question est **normalisée par défaut** (fautes de noms corrigées, question complète reformulée par le modèle ; elle s'affiche en gris quand elle diffère de la saisie, son temps est dans les statistiques) : `--no-rewrite` au lancement ou `/rewrite` pour la couper.

**Déroulé proposé (diapo « Démo »)** :
1. `/compare` puis « What is Roadhog's Chain Hook cooldown in 5v5 after the 6 October 2026 patch? »
   Sans RAG, le modèle invente (10 s lors du test) ; avec RAG, il répond « 7 → 6 s » depuis les notes officielles.
   **Avec le RAFT 4B v2 seulement** : le 1.7B confond la ligne 5v5 et la ligne 6v6 du même passage (il répond 8 → 7 s).
   Avec le 1.7B, prendre plutôt « Which role and sub-role did Sombra move to in the 6 October 2026 patch? » (réponse juste
   avec les deux modèles).
2. « What is the ultimate ability of the hero Kestrel? » : héros inventé, le modèle répond qu'il ne sait pas.
3. Une question du public.
4. Option parlante : **couper le Wi-Fi** avant la démo pour montrer que tout est local.

Conseils :
- Lancer le script avant de passer à la diapo : le chargement (modèle + index + embeddings) prend quelques secondes, ensuite
  le modèle reste en mémoire 60 min.
- Garder `/sources` actif : voir les passages trouvés aide à expliquer le RAG.
- Les réponses ont été vérifiées sur le PC (Ollama, GPU). Sur le Mac, le calcul diffère légèrement (Metal) : **refaire
  le déroulé complet sur le Mac la veille**, et noter la latence obtenue (elle n'a pas été mesurée sur Mac).
- **Plan B** : enregistrer la démo qui marche (Cmd + Maj + 5 sur macOS) et garder la vidéo ouverte dans un onglet.

## 4. Continuer le projet sur le Mac

| Tâche | Sur Mac | Remarque |
|---|---|---|
| Démo, requêtes RAG (`rag.cli query`) | oui | |
| Banc local (`bench.cli run` sur les configs Ollama), juge, rapport | oui | `claude -p` doit être connecté ; latences et débits différents du PC : ne pas les mélanger dans un même tableau |
| Bras frontier (`claude-sonnet`, `claude-sonnet-web`...) | oui | abonnement Claude |
| Rédaction (`docs/rendu_final.md`), deck | oui | |
| Réindexation RAG (`rag.cli index`) | oui | nécessite `data/chunks` et les templates : copier tout `data/` (sauf `data/train`, 16 Go) |
| Génération Q/R (`qwen3.6:35b-a3b`) | possible si ≥ 32 Go de mémoire unifiée | beaucoup plus lent que sur le PC |
| Fine-tuning (`train/`) | **non** | Unsloth + bitsandbytes exigent CUDA : PC sous WSL2 uniquement |
| Mesure électrique (`bench.power`) | **non** | lit `nvidia-smi` ; sur Mac, `sudo powermetrics` donnerait une mesure différente |

Différences avec les consignes de `CLAUDE.md` (écrites pour le PC) :
- Smart App Control, l'interpréteur uv « de base » et `PYTHONPATH` : sans objet sur Mac, utiliser `uv run ...`.
- WSL, `Start-Process`, fichiers `.bat` : sans objet ; les traitements longs se lancent avec `nohup ... &` (ils restent
  reprenables : append JSONL, fichiers STOP).
- Le Brain (`Année INFO5/VTI`) est local sur le Mac : `/wrapup` y fonctionne en mode local.

Tailles des autres dossiers de `data/` (non copiés par défaut) : `raw` 251 Mo, `clean` 27 Mo, `chunks` 27 Mo, `qa` 44 Mo,
`dataset` 451 Mo, `backup` 178 Mo, `train` 16 Go (checkpoints et adapters : inutiles sur Mac, seuls les GGUF servent).
