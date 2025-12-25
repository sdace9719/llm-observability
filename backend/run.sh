set -a
source .env
set +a
ddtrace-run python main.py