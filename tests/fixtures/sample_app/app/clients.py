import sqlite3

import openai
import redis
import requests
from fastapi import FastAPI

api = FastAPI()


def ask(prompt: str) -> str:
    client = openai.OpenAI()
    reply = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return reply.choices[0].message.content


def cache() -> redis.Redis:
    return redis.Redis.from_url("redis://localhost:6379/0")


def github_user(name: str) -> dict:
    return requests.get(f"https://api.github.com/users/{name}", timeout=10).json()


def db():
    return sqlite3.connect("app.db")


@api.get("/health")
def health() -> dict:
    return {"ok": True}
