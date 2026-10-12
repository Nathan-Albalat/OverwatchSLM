. ~/venvs/unsloth/bin/activate
mkdir -p ~/work && cd ~/work
export PYTHONPATH=/mnt/c/Users/albal/Projet/SLM PYTHONUNBUFFERED=1
python -m train.cli export "$@"
