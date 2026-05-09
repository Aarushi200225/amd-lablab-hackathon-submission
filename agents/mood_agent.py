import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import re
from core.llm import llm_call
from pydantic import BaseModel
from core.guardrails import sanitize_output

class MoodObject(BaseModel):
    primary: str        # e.g. "anxious", "calm", "low", "hopeful"
    energy: str         # "low", "medium", "high"
    readiness: str      # "low", "medium", "high" — drives meal decision
    tone: str           # "grounding", "nudge", "celebratory" — drives card tone


SYSTEM_PROMPT = """
You are a gentle, emotionally intelligent assistant helping someone in eating disorder recovery.

Your job is to read the user's daily check-in (which may be text, emojis, or both) and classify their emotional state into a structured JSON object.

Rules:
- Be generous and warm in your interpretation
- Never assume the worst — "okay" is medium, not low
- Emojis count as valid emotional signals
- Return ONLY valid JSON, no explanation, no extra text

Return exactly this format:
{
    "primary": "one word emotion e.g. anxious / calm / low / hopeful / okay / happy / tired, etc.",
    "energy": "low or medium or high",
    "readiness": "low or medium or high",
    "tone": "grounding or nudge or celebratory"
}

Tone guide:
- grounding → for anxious, overwhelmed, low, tired
- nudge → for okay, neutral, unsure, medium energy
- celebratory → for happy, hopeful, good, high energy
"""


def parse_mood_response(raw: str) -> dict:
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
def run_mood_agent(user_input: str) -> MoodObject:
    user_prompt = f"Here is today's check-in: {user_input}"
    
    raw_response = llm_call(SYSTEM_PROMPT, user_prompt)
    mood_dict = parse_mood_response(raw_response)
    
    return MoodObject(**mood_dict)