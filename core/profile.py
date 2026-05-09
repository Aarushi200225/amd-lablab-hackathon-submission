import sqlite3
import json
from datetime import date
from pathlib import Path

DB_PATH = Path("data/nourish.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY,
            name TEXT,
            disorder_category TEXT,
            trigger_foods TEXT,
            safe_foods TEXT,
            challenge_foods TEXT,
            comfort_foods TEXT,
            personality_traits TEXT,
            health_context TEXT,
            start_date TEXT,
            current_phase INTEGER DEFAULT 30
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            day_number INTEGER,
            mood_input TEXT,
            mood_classified TEXT,
            card_output TEXT,
            meal_suggestion TEXT,
            challenge_food_suggested INTEGER DEFAULT 0,
            journal_note TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_profile(data: dict):
    conn = get_connection()
    cursor = conn.cursor()

    # lists get stored as JSON strings — easy to read back later
    cursor.execute("""
        INSERT OR REPLACE INTO user_profile (
            id, name, disorder_category,
            trigger_foods, safe_foods, challenge_foods, comfort_foods,
            personality_traits, health_context, start_date, current_phase
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["name"],
        data["disorder_category"],
        json.dumps(data["trigger_foods"]),
        json.dumps(data["safe_foods"]),
        json.dumps(data["challenge_foods"]),
        json.dumps(data["comfort_foods"]),
        json.dumps(data["personality_traits"]),
        data["health_context"],
        str(date.today()),
        data["current_phase"]
    ))

    conn.commit()
    conn.close()


def load_profile() -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "name": row["name"],
        "disorder_category": row["disorder_category"],
        "trigger_foods": json.loads(row["trigger_foods"]),
        "safe_foods": json.loads(row["safe_foods"]),
        "challenge_foods": json.loads(row["challenge_foods"]),
        "comfort_foods": json.loads(row["comfort_foods"]),
        "personality_traits": json.loads(row["personality_traits"]),
        "health_context": row["health_context"],
        "start_date": row["start_date"],
        "current_phase": row["current_phase"]
    }


def profile_exists() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user_profile WHERE id = 1")
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def get_day_number() -> int:
    profile = load_profile()
    if not profile:
        return 1
    start = date.fromisoformat(profile["start_date"])
    return (date.today() - start).days + 1