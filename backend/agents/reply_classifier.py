from __future__ import annotations

from openai import AsyncOpenAI

from backend.config import settings
from backend.ingestion.embedder import retry_async


VALID_INTENTS = {"SATISFIED", "STUCK", "UNCLEAR"}

SYSTEM_PROMPT = """You are classifying customer support replies. Respond with exactly one word.

SATISFIED — customer confirms the issue is resolved, says thank you, or asks to close the case.
Examples: "thank you", "that worked", "issue is resolved", "please close this ticket"

STUCK — customer says the solution did not work or reports a new specific technical error.
Examples: "still getting the error", "it didn't work", "now I see a different error"
Important: Do NOT classify as STUCK if the customer is asking for a call, a meeting,
or human assistance. Those are UNCLEAR.

UNCLEAR — you cannot determine intent, OR the customer is asking for a call, a chat,
a meeting, or to speak to a human.
Examples: "lets get on a webex call", "can we schedule a call", "I need to speak to someone",
"can you call me", "let's hop on a call", "can we meet"

Respond with only the word: SATISFIED, STUCK, or UNCLEAR."""


async def classify_reply(
    reply_text: str,
    client: AsyncOpenAI | None = None,
) -> str:
    openai_client = client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def call_openai() -> str:
        response = await openai_client.chat.completions.create(
            model=settings.openai_llm_model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": reply_text},
            ],
        )
        result = (response.choices[0].message.content or "").strip().upper()
        return result if result in VALID_INTENTS else "UNCLEAR"

    return await retry_async(call_openai, "OpenAI reply classification")
