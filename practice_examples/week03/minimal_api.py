"""minimal_api.py — Week 3 practice.
Distilled from  Week3.zip -> Week 3/demo_files/Demo Files/reference/api_main_reference.py
(app + Question model + endpoint shape + /health, lines 18-52 & 74-76), with the
pipeline dependency removed so you can feel FastAPI routing + validation in isolation.

Run (from the repo root):
    uvicorn practice_examples.week03.minimal_api:app --reload --port 8001
"""
from fastapi import FastAPI
from pydantic import BaseModel


class Question(BaseModel):          # ref lines 36-38
    question: str


app = FastAPI(title="Minimal API (practice)")   # ref lines 48-52 (simplified)


@app.post("/echo")                  # shape of @app.post from ref line 58, no pipeline
async def echo(q: Question):
    return {"you_asked": q.question}


@app.get("/health")                 # ref lines 74-76 (verbatim)
async def health():
    return {"status": "ok"}
