"""hello_llm.py — Week 1 practice: our first call to an LLM.

Run from the repo root:
    python practice_examples/week01/hello_llm.py "What is RAG in one sentence?"
"""
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()          # loads OPENAI_API_KEY from .env on your own machine
client = OpenAI()      # finds the key in the environment automatically


def ask(question: str) -> str:
    """Send one question to the model, return the answer text."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Say hello in one sentence."
    print(ask(q))
