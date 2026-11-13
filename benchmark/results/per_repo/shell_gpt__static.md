# shell_gpt — static

TP 1 · FP 3 · FN 1

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `openai/chat-completions` | `openai-compatible/chat-completions` | evidence | sgpt/handlers/handler.py:31, sgpt/handlers/handler.py:123, sgpt/handlers/handler.py:171, tests/utils.py:28, tests/utils.py:33 | sgpt/handlers/handler.py:31, sgpt/handlers/handler.py:123, sgpt/config.py:35 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|
| `click/sdk` | unknown | sgpt/app.py:190 · click.UsageError · known_sdk; sgpt/app.py:195 · click.UsageError · known_sdk; sgpt/app.py:198 · click.UsageError · known_sdk; sgpt/app.py:246 · click.types.Choice · known_sdk; sgpt/config.py:93 · click.UsageError · known_sdk; sgpt/handlers/chat_handler.py:154 · click.BadParameter · known_sdk; sgpt/handlers/chat_handler.py:160 · click.UsageError · known_sdk; sgpt/role.py:79 · click.UsageError · known_sdk …(+2) |
| `distro/sdk` | unknown | sgpt/role.py:120 · distro.name · known_sdk |
| `prompt-toolkit/sdk` | unknown | sgpt/app.py:241 · prompt_toolkit.PromptSession · known_sdk; sgpt/app.py:256 · prompt_toolkit.PromptSession().prompt · known_sdk |

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
| `litellm/completion` | True | sgpt/handlers/handler.py:24; sgpt/handlers/handler.py:26; pyproject.toml:38 | Optional provider selected by USE_LITELLM config flag; routes to whatever provider the model string names (README mentions Ollama/local LLMs, Azure via wiki). Labeled as multi-provider library; hostin |
