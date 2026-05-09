TRIGGER_TERMS = [
    "calories", "calorie", "weight", "bmi", "fat", "thin",
    "diet", "portions", "macros", "restriction", "purge",
    "binge", "body", "appearance", "slim", "obese", "skinny",
    "overweight", "underweight", "intake", "deficit"
]

FALLBACK_RESPONSES = {
    "card": "You showed up today. That's the whole job, and it's enough!!!",
    "meal": "Something warm and familiar sounds perfect for today.",
    "moodboard": "Today's palette is soft and yours — exactly what you need.",
    "progress": "Every day you're here is a day worth celebrating. Keep going!!!"
}


def is_safe_output(text: str) -> bool:
    return not any(term in text.lower() for term in TRIGGER_TERMS)


def sanitize_output(text: str, agent_name: str) -> str:
    if not is_safe_output(text):
        return FALLBACK_RESPONSES.get(agent_name, "You're doing great. Keep going!!!")
    return text