"""General alias table: top-level import name of a common SDK -> (canonical_name, hosting).

Used by prepare.py (static resolution in hybrid/static modes) and merge.py (name
normalization). General knowledge only — not derived from any benchmark repo. Anything not
listed here is named by the LLM (package-level in hybrid mode).

Cloud SDKs whose service depends on the call (boto3, google.cloud, azure) are named from
the call itself in `sdk_component()`.
"""

from __future__ import annotations

import re

# import top-level -> (canonical_name, hosting)
SDK_ALIASES: dict[str, tuple[str, str]] = {
    # LLM / AI APIs
    "anthropic": ("anthropic/messages", "cloud"),
    "openai": ("openai/chat-completions", "cloud"),
    "cohere": ("cohere/api", "cloud"),
    "mistralai": ("mistral/api", "cloud"),
    "groq": ("groq/api", "cloud"),
    "together": ("together/api", "cloud"),
    "replicate": ("replicate/api", "cloud"),
    "voyageai": ("voyage/embeddings", "cloud"),
    "ollama": ("ollama/chat", "self-hosted"),
    "huggingface_hub": ("huggingface/hub", "cloud"),
    "fastembed": ("fastembed/text-embedding", "self-hosted"),
    # databases / stores
    "redis": ("redis/redis", "self-hosted"),
    "psycopg": ("postgresql/database", "self-hosted"),
    "psycopg2": ("postgresql/database", "self-hosted"),
    "asyncpg": ("postgresql/database", "self-hosted"),
    "pymysql": ("mysql/database", "self-hosted"),
    "MySQLdb": ("mysql/database", "self-hosted"),
    "pymongo": ("mongodb/database", "self-hosted"),
    "motor": ("mongodb/database", "self-hosted"),
    "elasticsearch": ("elastic/elasticsearch", "self-hosted"),
    "cassandra": ("apache/cassandra", "self-hosted"),
    "neo4j": ("neo4j/database", "self-hosted"),
    # vector DBs
    "pinecone": ("pinecone/vector-db", "cloud"),
    "qdrant_client": ("qdrant/vector-db", "self-hosted"),
    "weaviate": ("weaviate/vector-db", "self-hosted"),
    "chromadb": ("chroma/vector-db", "self-hosted"),
    # messaging / queues
    "kafka": ("apache/kafka", "self-hosted"),
    "confluent_kafka": ("apache/kafka", "self-hosted"),
    "pika": ("rabbitmq/amqp", "self-hosted"),
    "nats": ("nats/messaging", "self-hosted"),
    # SaaS APIs
    "stripe": ("stripe/payments", "cloud"),
    "twilio": ("twilio/api", "cloud"),
    "sendgrid": ("sendgrid/email", "cloud"),
    "slack_sdk": ("slack/web-api", "cloud"),
    "github": ("github/rest-api", "cloud"),
    "supabase": ("supabase/api", "cloud"),
    "firebase_admin": ("google/firebase", "cloud"),
    "sentry_sdk": ("sentry/errors", "cloud"),
    # local browsers / containers
    "playwright": ("playwright/chromium", "self-hosted"),
    "selenium": ("selenium/webdriver", "self-hosted"),
    "docker": ("docker/engine", "self-hosted"),
}

# Normalize equivalent spellings an LLM may produce for the same service.
NAME_SYNONYMS: dict[str, str] = {
    "hugging-face": "huggingface",
    "hf": "huggingface",
    "amazon": "aws",
    "amazon-web-services": "aws",
    "google-cloud": "gcp",
    "postgres": "postgresql",
}

# Constructor keywords that point an SDK at a non-default endpoint (D-29).
ENDPOINT_KWARGS = {"base_url", "api_base", "base", "host", "endpoint", "url", "server_url", "api_url"}


def _first_literal(args: list[str]) -> str | None:
    if args and re.fullmatch(r"""(['"])[A-Za-z0-9_.-]+\1""", args[0]):
        return args[0][1:-1]
    for a in args:
        m = re.fullmatch(r"""service_name=(['"])([A-Za-z0-9_.-]+)\1""", a)
        if m:
            return m.group(2)
    return None


def sdk_component(top: str, callee: str, args: list[str]) -> tuple[str, str] | None:
    """canonical_name + hosting for a static SDK call, or None if not in the alias table."""
    if top in ("boto3", "botocore", "aioboto3"):
        service = _first_literal(args) if re.search(r"\b(client|resource)$", callee.split("(")[0]) else None
        return (f"aws/{service.lower()}" if service else "aws/sdk"), "cloud"
    if callee.startswith("google.cloud."):
        product = callee.split(".")[2]
        return f"gcp/{product.replace('_', '-')}", "cloud"
    if callee.startswith(("google.generativeai", "google.genai")):
        return "google/gemini", "cloud"
    if callee.startswith("azure."):
        parts = callee.split(".")
        product = parts[2] if len(parts) > 2 and parts[1] in ("storage", "ai", "cosmos", "servicebus", "keyvault") else parts[1]
        return f"azure/{product.replace('_', '-')}", "cloud"
    return SDK_ALIASES.get(top)


def normalize_name(name: str | None) -> str | None:
    """Lowercase, hyphenate, and map known synonyms in the provider part."""
    if not name:
        return name
    name = re.sub(r"[\s_]+", "-", name.strip().lower())
    provider, _, service = name.partition("/")
    provider = NAME_SYNONYMS.get(provider, provider)
    return f"{provider}/{service}" if service else provider


if __name__ == "__main__":  # self-check
    assert sdk_component("boto3", "boto3.client", ["'s3'"]) == ("aws/s3", "cloud")
    assert sdk_component("boto3", "boto3.client().put_object", ["Bucket=b"]) == ("aws/sdk", "cloud")
    assert sdk_component("google", "google.cloud.bigquery.Client", []) == ("gcp/bigquery", "cloud")
    assert sdk_component("anthropic", "anthropic.Anthropic().messages.create", []) == ("anthropic/messages", "cloud")
    assert sdk_component("pydantic", "pydantic.Field", []) is None
    assert normalize_name("Hugging Face/Hub") == "huggingface/hub"
    print("aliases selfcheck ok")
