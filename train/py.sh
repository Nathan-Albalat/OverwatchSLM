. ~/venvs/unsloth/bin/activate
cd "${WORKDIR:-/mnt/c/Users/albal/Projet/SLM}"
export PYTHONPATH=/mnt/c/Users/albal/Projet/SLM PYTHONUNBUFFERED=1
python -m train.cli "$@"
