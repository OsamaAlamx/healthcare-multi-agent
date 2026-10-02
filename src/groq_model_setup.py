"""
One-time setup helper: selects a working Groq chat model, writes it into
.env as GROQ_MODEL, and verifies it with a test completion.

Run from src/:
    python groq_model_setup.py
"""
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

PREFERRED_MODELS = [
    "openai/gpt-oss-120b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "moonshotai/kimi-k2-instruct",
    "llama-3.1-8b-instant",
]


def main():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SystemExit("GROQ_API_KEY is missing from .env")

    client = Groq(api_key=api_key)
    available = sorted(m.id for m in client.models.list().data)

    print("Models available to your key:")
    for m in available:
        print(f"  {m}")

    chosen = next((m for m in PREFERRED_MODELS if m in available), None)
    if not chosen:
        raise SystemExit(
            "No preferred model is available. Pick one from the list above "
            "and set GROQ_MODEL=<name> in .env manually."
        )

    print(f"Selected model: {chosen}")

    lines = []
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            lines = [
                line for line in f.read().splitlines()
                if not line.strip().upper().startswith("GROQ_MODEL")
            ]
    lines.append(f"GROQ_MODEL={chosen}")
    with open(".env", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Updated .env -> GROQ_MODEL={chosen}")

    response = client.chat.completions.create(
        model=chosen,
        messages=[{"role": "user", "content": "Say OK"}],
    )
    print(f"LLM test passed, reply: {response.choices[0].message.content}")


if __name__ == "__main__":
    main()