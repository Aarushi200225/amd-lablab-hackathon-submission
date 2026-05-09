import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from core.profile import get_connection, get_day_number


def save_daily_log(
    mood_input: str,
    mood_classified: dict,
    card_output: dict,
    meal_suggestion: dict,
    challenge_food_suggested: bool,
    journal_note: str = ""
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO daily_log (
            date,
            day_number,
            mood_input,
            mood_classified,
            card_output,
            meal_suggestion,
            challenge_food_suggested,
            journal_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(date.today()),
        get_day_number(),
        mood_input,
        json.dumps(mood_classified),
        json.dumps(card_output),
        json.dumps(meal_suggestion),
        1 if challenge_food_suggested else 0,
        journal_note
    ))

    conn.commit()
    conn.close()


def log_already_exists_today() -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM daily_log
        WHERE date = ?
    """, (str(date.today()),))

    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def load_today_log() -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM daily_log
        WHERE date = ?
    """, (str(date.today()),))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "date": row["date"],
        "day_number": row["day_number"],
        "mood_input": row["mood_input"],
        "mood_classified": json.loads(row["mood_classified"]),
        "card_output": json.loads(row["card_output"]),
        "meal_suggestion": json.loads(row["meal_suggestion"]),
        "challenge_food_suggested": bool(row["challenge_food_suggested"]),
        "journal_note": row["journal_note"]
    }


def get_weekly_mood_history() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    week_ago = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT date, day_number, mood_input,
               mood_classified, challenge_food_suggested
        FROM daily_log
        WHERE date >= ?
        ORDER BY date ASC
    """, (week_ago,))

    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "date": row["date"],
            "day_number": row["day_number"],
            "mood_input": row["mood_input"],
            "mood_classified": json.loads(row["mood_classified"]),
            "challenge_food_suggested": bool(row["challenge_food_suggested"])
        })

    return history


def get_all_logs() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT date, day_number, mood_input,
               mood_classified, challenge_food_suggested
        FROM daily_log
        ORDER BY date ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "date": row["date"],
            "day_number": row["day_number"],
            "mood_input": row["mood_input"],
            "mood_classified": json.loads(row["mood_classified"]),
            "challenge_food_suggested": bool(row["challenge_food_suggested"])
        }
        for row in rows
    ]


def update_journal_note(journal_note: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE daily_log
        SET journal_note = ?
        WHERE date = ?
    """, (journal_note, str(date.today())))

    conn.commit()
    conn.close()