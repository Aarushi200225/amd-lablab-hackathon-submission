import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import re
import sqlite3
from datetime import datetime, timedelta
from pydantic import BaseModel
from core.llm import llm_call
from core.profile import load_profile, get_day_number, get_connection
from core.guardrails import sanitize_output

class ProgressOutput(BaseModel):
    progress_note: str
    milestone_hit: bool
    milestone_day: int | None
    context_for_card: str


SYSTEM_PROMPT = """
You are Nour — a warm, enthusiastic, deeply caring companion supporting someone 
in their healing journey. You write short, heartfelt progress notes that feel 
like a message from a best friend who genuinely sees and celebrates every step.

Your note must follow this exact structure with these constant headings:

🌟 WHERE YOU ARE
One warm sentence about their day in the journey.

💪 THIS WEEK'S WINS
2-3 sentences about mood patterns and consistency, 
framed as wins — never as failures or numbers.

🍽️ BRAVE MOMENTS
One sentence celebrating any challenge food attempts, 
framed purely around courage — never around food itself.

✨ YOUR VIBE CHECK
One sentence that's pure hype — their energy, their glow, 
their comeback. Make it punchy and real!!!

💌 FROM NOUR
One closing line — warm, personal, like a note slipped 
under the door from someone who believes in them completely.

Strict rules — never break these:
- No calories, weights, portions, macros, body appearance
- No numerical scores or percentage improvements  
- No mention of missed days or gaps
- No clinical language
- Frame everything as narrative and warmth
- Use exclamation marks naturally!!
- Return ONLY the formatted note, no JSON, no extra text
"""


def get_weekly_mood_history() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    week_ago = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT date, day_number, mood_classified, 
               challenge_food_suggested
        FROM daily_log
        WHERE date >= ?
        ORDER BY date ASC
    """, (week_ago,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_challenge_food_attempts() -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as attempts 
        FROM daily_log 
        WHERE challenge_food_suggested = 1
    """)
    result = cursor.fetchone()
    conn.close()
    return result["attempts"] if result else 0


def check_milestone(day_number: int) -> int | None:
    milestones = [7, 14, 30, 60, 90]
    return day_number if day_number in milestones else None


def summarize_mood_history(history: list[dict]) -> str:
    if not history:
        return "just getting started"

    moods = [h["mood_classified"] for h in history if h["mood_classified"]]
    grounded = ["calm", "okay", "hopeful", "happy", "good"]
    grounded_days = sum(1 for m in moods if any(g in str(m).lower() for g in grounded))

    return f"{grounded_days} grounded days out of {len(history)} this week"


def build_user_prompt(
    profile: dict,
    day_number: int,
    mood_summary: str,
    challenge_attempts: int,
    milestone: int | None
) -> str:
    milestone_note = f"TODAY IS A MILESTONE — Day {milestone}!!!" if milestone else "No milestone today."

    return f"""
Here's everything you know about this person's journey:

Name: {profile['name']}
Current day: Day {day_number} of {profile['current_phase']}
Disorder context: {profile['disorder_category']}
Personality traits: {', '.join(profile['personality_traits'])}

This week's mood summary: {mood_summary}
Total brave challenge food moments so far: {challenge_attempts}
{milestone_note}

Write their progress note using the exact structure provided.
Make it feel like a warm, personal message from their most 
supportive friend — Nour. Use their name naturally throughout.
If today is a milestone, make the note extra celebratory!!!
"""


def run_progress_agent() -> ProgressOutput:
    profile = load_profile()
    day_number = get_day_number()

    history = get_weekly_mood_history()
    mood_summary = summarize_mood_history(history)
    challenge_attempts = get_challenge_food_attempts()
    milestone = check_milestone(day_number)

    user_prompt = build_user_prompt(
        profile,
        day_number,
        mood_summary,
        challenge_attempts,
        milestone
    )

    progress_note = llm_call(SYSTEM_PROMPT, user_prompt)

    context_for_card = f"Day {day_number} of {profile['current_phase']}"
    if milestone:
        context_for_card += f" — milestone day, celebratory tone"

    return ProgressOutput(
        progress_note=sanitize_output(progress_note.strip(), "progress"),
        milestone_hit=milestone is not None,
        milestone_day=milestone,
        context_for_card=sanitize_output(context_for_card, "progress")
    )