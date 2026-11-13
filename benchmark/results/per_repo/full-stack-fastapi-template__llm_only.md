# full-stack-fastapi-template — llm_only

TP 3 · FP 0 · FN 0

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `postgresql/database` | `postgresql/database` | name | backend/app/alembic/env.py:68, backend/app/alembic/env.py:74, backend/app/alembic/env.py:86, backend/app/api/routes/login.py:30, backend/app/api/routes/login.py:58 | backend/app/core/db.py:7, backend/app/core/config.py:39, .env:18 |
| `smtp/email` | `smtp/email` | name | backend/app/api/routes/login.py:67, backend/app/api/routes/users.py:73, backend/app/utils.py:56 | backend/app/utils.py:56, backend/app/core/config.py:45, .env:11 |
| `sentry/errors` | `sentry/error-tracking` | evidence | backend/app/main.py:19 | backend/app/main.py:19, backend/app/core/config.py:30, compose.yml:65 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
