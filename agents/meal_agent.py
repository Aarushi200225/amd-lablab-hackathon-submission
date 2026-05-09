import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))

import json
import re
import os
import requests
from pydantic import BaseModel
from core.llm import llm_call
from core.profile import load_profile, get_day_number
from agents.mood_agent import MoodObject
from core.guardrails import sanitize_output
from dotenv import load_dotenv

load_dotenv('x.env')

SPOONACULAR_KEY = os.getenv("SPOONACULAR_API_KEY")


class MealOutput(BaseModel):
    dish_name: str
    description: str
    why_today: str
    sensory_note: str
    social_nudge: str
    challenge_level: str  # "safe", "gentle_push", "challenge"
    recipe_image: str | None = None
    ingredients_preview: list[str] | None = None


SYSTEM_PROMPT = """
You are a warm, deeply emotionally intelligent companion who combines the empathy of a therapist, the knowledge of a nutritionist, and the creativity of a chef. You support people in eating disorder recovery.

Your job today is to suggest ONE dish for the person based on everything you know about them — their mood, their food history, their readiness, and their recovery journey.

Your core decision logic:
- readiness low → always suggest a safe or comfort food, framed with warmth and zero pressure
- readiness medium → suggest a safe food with one small new or interesting element
- readiness high → gently introduce a challenge food, framed purely around taste and curiosity
- trigger foods → NEVER suggested under any circumstance, regardless of anything else

Your framing rules — never break these:
- No calories, weights, portions, macros, or nutritional breakdowns
- No body-related language or appearance comments
- No clinical advice or prescriptive language
- Frame everything around taste, color, warmth, texture, smell, and curiosity
- The social nudge should always be light and optional — never obligatory
- Speak like a warm, creative, emotionally aware friend

If the person had a difficult previous day, today's suggestion should feel softer and more familiar — without explicitly referencing what happened.

Return ONLY valid JSON in exactly this format, no extra text:
{
    "dish_name": "...",
    "description": "one warm sentence about the dish",
    "why_today": "one sentence on why this dish fits today emotionally",
    "sensory_note": "one sensory observation to notice while eating",
    "social_nudge": "a light, optional, enthusiastic nudge to share it",
    "challenge_level": "safe or gentle_push or challenge"
}
"""


def build_user_prompt(mood: MoodObject, profile: dict, day_number: int) -> str:
    return f"""
Here's everything you know about this person today:

Name: {profile['name']}
Day in journey: Day {day_number} of {profile['current_phase']}
Disorder context: {profile['disorder_category']}
Personality traits: {', '.join(profile['personality_traits'])}

Today's mood: {mood.primary}
Energy level: {mood.energy}
Readiness level: {mood.readiness}

Their food world:
- Safe foods: {', '.join(profile['safe_foods'])}
- Comfort foods: {', '.join(profile['comfort_foods'])}
- Challenge foods (work toward gently): {', '.join(profile['challenge_foods'])}
- Trigger foods (NEVER suggest these): {', '.join(profile['trigger_foods'])}

Based on all of this, suggest one dish for today.
Remember — readiness is {mood.readiness}, so choose the challenge level accordingly.
Frame everything around taste, warmth, color, texture. Keep it creative and genuinely exciting!
"""


def fetch_recipe_visuals(dish_name: str) -> tuple[str | None, list[str] | None]:
    if not SPOONACULAR_KEY:
        return None, None

    try:
        response = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params={
                "query": dish_name,
                "number": 1,
                "addRecipeInformation": False,
                "apiKey": SPOONACULAR_KEY
            },
            timeout=5
        )
        data = response.json()
        results = data.get("results", [])

        if not results:
            return None, None

        recipe_id = results[0]["id"]
        image_url = results[0].get("image")

        # download image locally
        local_image_path = None
        if image_url:
            img_response = requests.get(image_url, timeout=10)
            if img_response.status_code == 200:
                from pathlib import Path
                meal_img_dir = Path("data/generated_images")
                meal_img_dir.mkdir(parents=True, exist_ok=True)
                local_image_path = str(meal_img_dir / ("meal_" + dish_name[:20].replace(" ", "_") + ".jpg"))
                with open(local_image_path, "wb") as img_file:
                    img_file.write(img_response.content)

        # fetch ingredients
        info = requests.get(
            "https://api.spoonacular.com/recipes/" + str(recipe_id) + "/ingredientWidget.json",
            params={"apiKey": SPOONACULAR_KEY},
            timeout=5
        )
        ingredients_data = info.json().get("ingredients", [])
        ingredient_names = [i["name"] for i in ingredients_data[:6]]

        return local_image_path, ingredient_names

    except Exception as meal_error:
        print("[meal] fetch failed: " + str(meal_error))
        return None, None

    try:
        response = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params={
                "query": dish_name,
                "number": 1,
                "addRecipeInformation": False,
                "apiKey": SPOONACULAR_KEY
            },
            timeout=5
        )
        data = response.json()
        results = data.get("results", [])

        if not results:
            return None, None

        recipe_id = results[0]["id"]
        image = results[0].get("image")

        # fetch ingredients — strip any numeric/metric language
        info = requests.get(
            f"https://api.spoonacular.com/recipes/{recipe_id}/ingredientWidget.json",
            params={"apiKey": SPOONACULAR_KEY},
            timeout=5
        )
        ingredients_data = info.json().get("ingredients", [])

        # only return ingredient names — no amounts, no units
        ingredient_names = [i["name"] for i in ingredients_data[:6]]

        return image, ingredient_names

    except Exception:
        # if spoonacular fails, meal agent still works fine without it
        return None, None


def parse_meal_response(raw: str) -> dict:
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
def run_meal_agent(mood: MoodObject) -> MealOutput:
    profile = load_profile()
    day_number = get_day_number()

    user_prompt = build_user_prompt(mood, profile, day_number)
    raw_response = llm_call(SYSTEM_PROMPT, user_prompt)
    meal_dict = parse_meal_response(raw_response)

    # fetch visuals from spoonacular — gracefully optional
    image, ingredients = fetch_recipe_visuals(meal_dict["dish_name"])

    return MealOutput(
        dish_name=meal_dict["dish_name"],
        description=sanitize_output(meal_dict["description"], "meal"),
        why_today=sanitize_output(meal_dict["why_today"], "meal"),
        sensory_note=sanitize_output(meal_dict["sensory_note"], "meal"),
        social_nudge=sanitize_output(meal_dict["social_nudge"], "meal"),
        challenge_level=meal_dict["challenge_level"],
        recipe_image=image,
        ingredients_preview=ingredients
    )