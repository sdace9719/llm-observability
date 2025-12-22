export DD_SERVICE="vertex-chat-bot"  # The name of your backend
export DD_ENV="dev"                  # The environment filter
export DD_LLMOBS_ENABLED=1
export DD_LLMOBS_ML_APP=vertex-chat-bot
export DD_API_KEY=431f10b5-cd7e-4bd4-86b2-b511a1175ddc
export DD_SITE="us5.datadoghq.com"
export DD_RUNTIME_METRICS_ENABLED=1
ddtrace-run python main.py