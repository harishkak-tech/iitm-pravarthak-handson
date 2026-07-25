"""streaming_demo.py — Week 3 practice.
Distilled from  Week3.zip -> Week 3/demo_files/Demo Files/reference/api_main_reference.py
(the stream_answer generator + StreamingResponse, lines 82-103), with the pipeline
removed so you can feel the streaming machinery in isolation. Streams a fixed answer.

Run (from the repo root):
    uvicorn practice_examples.week03.streaming_demo:app --reload --port 8002
"""
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Streaming demo (practice)")

ANSWER = "Streaming sends the answer piece by piece so it feels fast to the end user. Non streaming is good for downstream applications and streaming is good when the API is directly returning to UI."


class Question(BaseModel):
    question: str


async def stream_answer(text: str):          # ref lines 82-93 (shape), no pipeline
    for word in text.split(" "):
        yield word + " "
        await asyncio.sleep(0.5)


@app.post("/ask")                            # ref lines 96-103 (simplified)
async def ask(q: Question):
    return StreamingResponse(stream_answer(ANSWER), media_type="text/plain")
