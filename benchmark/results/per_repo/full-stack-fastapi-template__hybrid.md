# full-stack-fastapi-template — hybrid

TP 3 · FP 0 · FN 0

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `postgresql/database` | `postgresql/database` | name | backend/app/alembic/env.py:68, backend/app/alembic/env.py:74, backend/app/alembic/env.py:86, backend/app/alembic/versions/1a31ce608336_add_cascade_delete_relationships.py:23, backend/app/alembic/versions/1a31ce608336_add_cascade_delete_relationships.py:35 | backend/app/core/db.py:7, backend/app/core/config.py:39, .env:18 |
| `smtp/email` | `smtp/email` | name | backend/app/utils.py:42, backend/app/utils.py:56 | backend/app/utils.py:56, backend/app/core/config.py:45, .env:11 |
| `sentry/errors` | `sentry/error-tracking` | evidence | backend/app/main.py:19 | backend/app/main.py:19, backend/app/core/config.py:30, compose.yml:65 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
