import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import re
from pydantic import BaseModel
from core.llm import llm_call
from core.profile import load_profile, get_day_number
from agents.mood_agent import MoodObject
from core.guardrails import sanitize_output

class CardOutput(BaseModel):
    hype_line: str
    micro_prompt: str
    day_marker: str


SYSTEM_PROMPT = """
You are Nour — a young, warm, and enthusiastic mental health professional who doubles as a hype best friend. You're full of energy, positivity, and genuine care. You use exclamation marks naturally, speak like a real person, and make whoever you're talking to feel genuinely seen and celebrated.

You're supporting someone in eating disorder recovery. Your job is to generate two things:
1. A personalised hype_line — warm, punchy, references their name and where they are in their journey
2. A micro_prompt — a small, sensory, curiosity-based nudge for the day. Always end it with a romanticised, glow-up flavoured phrase using "and romanticize..." or "and remember..." style endings

Strict rules — never break these:
- No mention of calories, weights, portions, macros, or body appearance
- No clinical language or advice
- Keep everything body-neutral and sensory
- Speak like a warm, enthusiastic friend — not a textbook
- Use punctuation and exclamation marks naturally!!
- Return ONLY valid JSON, no extra text

Return exactly this format:
{
    "hype_line": "...",
    "micro_prompt": "..."
}
"""


def build_user_prompt(mood: MoodObject, profile: dict, day_number: int) -> str:
    return f"""
Here's everything you know about this person today:

Name: {profile['name']}
Day in journey: Day {day_number} of {profile['current_phase']}
Personality traits: {', '.join(profile['personality_traits'])}
Disorder context: {profile['disorder_category']}
Today's mood: {mood.primary}
Energy level: {mood.energy}
Readiness level: {mood.readiness}
Tone needed: {mood.tone}

Generate a hype_line and micro_prompt for them today.
The hype_line should feel personal — use their name, reference their day number naturally.
The micro_prompt should be sensory, curiosity-based, and end with a romanticised glow-up phrase.
"""


def parse_card_response(raw: str) -> dict:
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
def run_card_agent(mood: MoodObject) -> CardOutput:
    profile = load_profile()
    day_number = get_day_number()

    user_prompt = build_user_prompt(mood, profile, day_number)
    raw_response = llm_call(SYSTEM_PROMPT, user_prompt)
    card_dict = parse_card_response(raw_response)

    return CardOutput(
        hype_line=sanitize_output(card_dict["hype_line"], "card"),
        micro_prompt=sanitize_output(card_dict["micro_prompt"], "card"),
        day_marker=f"Day {day_number} of {profile['current_phase']} 🔥"
    )