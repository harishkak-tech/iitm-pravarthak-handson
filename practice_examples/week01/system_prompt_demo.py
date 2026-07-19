"""system_prompt_demo.py — Week 1 practice: the power of one line (the system prompt).

Same question, four personalities. Only the system prompt changes.
    python practice_examples/week01/system_prompt_demo.py
"""
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

QUESTION = "Explain quantum entanglement in two sentences."
VOICES = {
    "concise":      "You are concise.",
    "kindergarten": "You are a kindergarten teacher. Explain like the listener is five.",
    "shakespeare":  "You are a Shakespearean poet. Reply in iambic verse where possible.",
    "physicist":    "You are a brilliant but impatient physicist. Accurate, no niceties.",
}

for name, system_prompt in VOICES.items():
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": QUESTION},
        ],
        temperature=0.7,
    )
    print(f"\n===== {name} =====\n{resp.choices[0].message.content}")
