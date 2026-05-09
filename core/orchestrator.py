import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

import traceback
from agents.mood_agent import run_mood_agent
from agents.card_agent import run_card_agent
from agents.meal_agent import run_meal_agent
from agents.moodboard_agent import run_moodboard_agent
from agents.progress_agent import run_progress_agent
from core.memory import save_daily_log, log_already_exists_today


def run_daily_card(user_input: str) -> dict:
    """
    Main orchestration pipeline.
    Runs all agents sequentially and returns
    combined output for the UI.
    """

    errors = []

    # ── 1. Mood — everything downstream depends on this ──────────────
    mood = run_mood_agent(user_input)

    # ── 2. Progress — reads history independently ────────────────────
    try:
        progress = run_progress_agent()
    except Exception as e:
        errors.append(f"progress: {e}")
        progress = None

    # ── 3. Card — needs mood ─────────────────────────────────────────
    try:
        card = run_card_agent(mood)
    except Exception as e:
        errors.append(f"card: {e}")
        card = None

    # ── 4. Meal — needs mood ─────────────────────────────────────────
    try:
        meal = run_meal_agent(mood)
    except Exception as e:
        errors.append(f"meal: {e}")
        meal = None

    # ── 5. Moodboard — needs mood + card ─────────────────────────────
    try:
        moodboard = run_moodboard_agent(mood, card) if card else None
    except Exception as e:
        errors.append(f"moodboard: {e}")
        moodboard = None

    # ── 6. Save daily log — only once per day ────────────────────────
    try:
        if not log_already_exists_today() and card and meal:
            save_daily_log(
                mood_input=user_input,
                mood_classified=mood.model_dump(),
                card_output=card.model_dump(),
                meal_suggestion=meal.model_dump(),
                challenge_food_suggested=(
                    meal.challenge_level != "safe"
                )
            )
    except Exception as e:
        errors.append(f"logging: {e}")

    # ── 7. Surface any non-critical errors for debugging ─────────────
    if errors:
        print(f"[orchestrator] non-critical errors: {errors}")

    return {
        "mood": mood,
        "card": card,
        "meal": meal,
        "moodboard": moodboard,
        "progress": progress
    }