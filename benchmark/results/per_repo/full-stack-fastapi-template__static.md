# full-stack-fastapi-template — static

TP 3 · FP 5 · FN 0

## True positives

| tool | label | matched by | tool evidence | label evidence |
|---|---|---|---|---|
| `sqlmodel/sdk` | `postgresql/database` | evidence | backend/app/alembic/versions/e2412789c190_initialize_models.py:23, backend/app/alembic/versions/e2412789c190_initialize_models.py:26, backend/app/alembic/versions/e2412789c190_initialize_models.py:29, backend/app/alembic/versions/e2412789c190_initialize_models.py:36, backend/app/alembic/versions/e2412789c190_initialize_models.py:38 | backend/app/core/db.py:7, backend/app/core/config.py:39, .env:18 |
| `emails/sdk` | `smtp/email` | evidence | backend/app/utils.py:42, backend/app/utils.py:56 | backend/app/utils.py:56, backend/app/core/config.py:45, .env:11 |
| `sentry/errors` | `sentry/error-tracking` | evidence | backend/app/main.py:19 | backend/app/main.py:19, backend/app/core/config.py:30, compose.yml:65 |

## False positives (tool only)

| tool | hosting | evidence (location · callee · route) |
|---|---|---|
| `app/sdk` | unknown | backend/app/api/routes/items.py:44 · app.models.ItemPublic.model_validate · known_sdk; backend/app/api/routes/items.py:45 · app.models.ItemsPublic · known_sdk; backend/app/api/routes/items.py:68 · app.models.Item.model_validate · known_sdk; backend/app/api/routes/items.py:113 · app.models.Message · known_sdk; backend/app/api/routes/login.py:30 · app.crud.authenticate · known_sdk; backend/app/api/routes/login.py:38 · app.models.Token · known_sdk; backend/app/api/routes/login.py:39 · app.core.security.create_access_token · known_sdk; backend/app/api/routes/login.py:58 · app.crud.get_user_by_email · known_sdk …(+122) |
| `jinja2/sdk` | unknown | backend/app/utils.py:29 · jinja2.Template · known_sdk; backend/app/utils.py:30 · jinja2.Template().render · known_sdk |
| `pwdlib/sdk` | unknown | backend/app/core/security.py:11 · pwdlib.PasswordHash · known_sdk; backend/app/core/security.py:13 · pwdlib.hashers.argon2.Argon2Hasher · known_sdk; backend/app/core/security.py:14 · pwdlib.hashers.bcrypt.BcryptHasher · known_sdk; backend/app/core/security.py:32 · pwdlib.PasswordHash().verify_and_update · known_sdk; backend/app/core/security.py:36 · pwdlib.PasswordHash().hash · known_sdk; backend/tests/api/routes/test_login.py:137 · pwdlib.hashers.bcrypt.BcryptHasher · known_sdk; backend/tests/api/routes/test_login.py:138 · pwdlib.hashers.bcrypt.BcryptHasher().hash · known_sdk; backend/tests/api/routes/test_login.py:139 · pwdlib.hashers.bcrypt.BcryptHasher().hash().startswith · known_sdk …(+3) |
| `pydantic-settings/sdk` | unknown | backend/app/core/config.py:16 · pydantic_settings.SettingsConfigDict · known_sdk |
| `sqlalchemy/sdk` | unknown | backend/app/alembic/env.py:68 · sqlalchemy.engine_from_config · known_sdk; backend/app/alembic/env.py:74 · sqlalchemy.engine_from_config().connect · known_sdk; backend/app/alembic/versions/1a31ce608336_add_cascade_delete_relationships.py:23 · sqlalchemy.UUID · known_sdk; backend/app/alembic/versions/1a31ce608336_add_cascade_delete_relationships.py:35 · sqlalchemy.UUID · known_sdk; backend/app/alembic/versions/9c0a54914c78_add_max_length_for_string_varchar_.py:23 · sqlalchemy.String · known_sdk; backend/app/alembic/versions/9c0a54914c78_add_max_length_for_string_varchar_.py:24 · sqlalchemy.String · known_sdk; backend/app/alembic/versions/9c0a54914c78_add_max_length_for_string_varchar_.py:29 · sqlalchemy.String · known_sdk; backend/app/alembic/versions/9c0a54914c78_add_max_length_for_string_varchar_.py:30 · sqlalchemy.String · known_sdk …(+45) |

## False negatives (label only)

| label | python evidence | evidence | label notes |
|---|---|---|---|
