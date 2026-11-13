# shell_gpt — llm_only

TP 1 · FP 1 · FN 1

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `openai-compatible/chat-completions` | `openai-compatible/chat-completions` | name | sgpt/handlers/handler.py:123, sgpt/handlers/handler.py:159 | sgpt/handlers/handler.py:31, sgpt/handlers/handler.py:123, sgpt/config.py:35 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|
| `openai/chat-completions` | cloud | sgpt/handlers/handler.py:31 · openai.OpenAI · known_sdk |

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
| `litellm/completion` | True | sgpt/handlers/handler.py:24; sgpt/handlers/handler.py:26; pyproject.toml:38 | Optional provider selected by USE_LITELLM config flag; routes to whatever provider the model string names (README mentions Ollama/local LLMs, Azure via wiki). Labeled as multi-provider library; hostin |
