import sys
from pathlib import Path

# makes sure Python can find core/, agents/ etc from anywhere
sys.path.append(str(Path(__file__).resolve().parent.parent))
import torch
from diffusers import StableDiffusionPipeline

import json
import re
import requests
from pydantic import BaseModel
from diffusers import FluxPipeline
from pydantic import BaseModel
from core.llm import creative_llm_call
from core.profile import load_profile, get_day_number
from agents.mood_agent import MoodObject
from agents.card_agent import CardOutput
from core.guardrails import sanitize_output
from huggingface_hub import login
from dotenv import load_dotenv
import os

load_dotenv('x.env')

# authenticate HF
HF_TOKEN = os.getenv("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

# output directory for generated images
OUTPUT_DIR = Path("data/generated_images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# print("[moodboard] loading FLUX.1-schnell...")

# _flux_pipeline = FluxPipeline.from_pretrained(
#     "black-forest-labs/FLUX.1-schnell",
#     torch_dtype=torch.bfloat16
# )
# _flux_pipeline = _flux_pipeline.to("cuda")

# print("[moodboard] FLUX.1-schnell loaded successfully")
_flux_pipeline = None
def get_flux_pipeline():
    global _flux_pipeline
    if _flux_pipeline is None:
        print("[moodboard] loading FLUX.1-schnell...")
        _flux_pipeline = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-schnell",
            torch_dtype=torch.bfloat16
        )
        _flux_pipeline = _flux_pipeline.to("cuda")
        print("[moodboard] FLUX loaded successfully")
    return _flux_pipeline

class ColorSwatch(BaseModel):
    hex: str
    name: str


class MoodboardOutput(BaseModel):
    palette: list[ColorSwatch]
    artwork_title: str
    artwork_artist: str | None
    artwork_image_url: str | None
    generated_image: str | None = None  # new field
    reflection: str
    palette_caption: str


# mood → abstract search keywords (no figurative/body terms)
MOOD_TO_ART_QUERY = {
    "anxious":     "soft mist calm water",
    "low":         "golden light quiet morning",
    "tired":       "gentle dusk warm glow",
    "okay":        "open sky soft breeze",
    "neutral":     "still lake pale morning",
    "hopeful":     "sunrise warm horizon",
    "happy":       "golden field bright bloom",
    "calm":        "soft light morning window",
    "celebratory": "vibrant bloom joyful color",
}

PALETTE_SYSTEM_PROMPT = """
You are a deeply creative color artist and poet. You specialize in art therapy, and have experience working in the mental health field. Your job is to generate a mood-based color palette for someone in their healing journey.

Generate exactly 4 colors that match the emotional tone provided.
Each color needs:
- A hex code that genuinely fits the mood
- A poetic, evocative name — 2-3 words maximum, lowercase
  Examples: "warm stillness", "soft exhale", "quiet morning", "golden push"

These names will be used as captions and thoughts of the day, so make them beautiful and meaningful.
Return ONLY a JSON object. No markdown. No explanation. No code blocks. No extra text before or after.
All strings must use double quotes. All arrays must be comma-separated properly.

Use exactly this structure:
{
    "palette": [
        {"hex": "#hexcode", "name": "poetic name"},
        {"hex": "#hexcode", "name": "poetic name"},
        {"hex": "#hexcode", "name": "poetic name"},
        {"hex": "#hexcode", "name": "poetic name"}
    ],
    "palette_caption": "one short poetic line using one of the color names as a thought of the day"
}

Rules:
- Exactly 4 colors
- hex must be a valid hex code starting with #
- name must be 2-3 words, lowercase, poetic
- palette_caption must be one short poetic sentence
- Return ONLY the JSON object, nothing else
"""

REFLECTION_SYSTEM_PROMPT = """
You are a warm, poetic companion supporting someone in their healing and self-discovery journey through art (art therapy).

Your job is to write a short 2-3 sentence reflection on a piece of artwork — written directly to the person, in second person present tense.

Style guide:
- Start with "Imagine yourself..." or "Picture yourself..." or "You are..."
- Use sensory language — light, warmth, texture, stillness, breath
- End with something affirming about the energy they deserve today
- Use "..." pauses naturally for a dreamy, unhurried feel
- Use exclamation marks at the end to bring warmth and energy!!

Rules:
- No body-related language or appearance comments
- No clinical language
- Keep it under 3 sentences
- No JSON, no markdown, no extra formatting
- Return ONLY the reflection text, nothing else
"""

def generate_moodboard_image(mood: str, palette_caption: str) -> str | None:
    # abstract prompt — no figurative or body-related content
    prompt = (
        f"abstract art, {mood} mood, soft aesthetic, "
        f"{palette_caption}, watercolor, dreamy, "
        f"no people, no faces, peaceful"
    )

    negative_prompt = (
        "people, faces, bodies, text, words, "
        "dark, scary, violent, realistic photo"
    )

    try:
        pipe = get_flux_pipeline()
        image = pipe(
            prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=4,
            guidance_scale=0.0,
            max_sequence_length=256
        ).images[0]

        global _flux_pipeline
        _flux_pipeline = None
        torch.cuda.empty_cache()

        # save locally and return path
        output_path = OUTPUT_DIR / f"moodboard_{mood}.png"
        image.save(output_path)
        return str(output_path)

    except Exception as e:
        print(f"[moodboard] SD generation failed: {e}")
        return None

def fetch_artwork(mood: str) -> tuple[str, str | None, str | None]:
    query = MOOD_TO_ART_QUERY.get(mood, "soft light abstract calm")
    try:
        # search Met Museum API
        search_response = requests.get(
            "https://collectionapi.metmuseum.org/public/collection/v1/search",
            params={"q": query, "hasImages": True},
            timeout=5
        )
        object_ids = search_response.json().get("objectIDs", [])
        if not object_ids:
            return "A quiet moment in light", None, None

        # try first few objects until we get a valid image
        for obj_id in object_ids[:5]:
            obj_response = requests.get(
                "https://collectionapi.metmuseum.org/public/collection/v1/objects/" + str(obj_id),
                timeout=5
            )
            obj_data = obj_response.json()
            image_url = obj_data.get("primaryImageSmall", "")
            if not image_url:
                continue

            img_response = requests.get(image_url, timeout=10)
            if img_response.status_code == 200:
                artwork_path = OUTPUT_DIR / ("artwork_" + mood + ".jpg")
                with open(str(artwork_path), "wb") as img_file:
                    img_file.write(img_response.content)
                return (
                    obj_data.get("title", "Untitled"),
                    obj_data.get("artistDisplayName", None),
                    str(artwork_path)
                )
    except Exception as fetch_error:
        print("[moodboard] art fetch failed: " + str(fetch_error))
    return "A quiet moment in light", None, None


def parse_palette_response(raw: str) -> dict:
       # clean any markdown code blocks if present
    raw = raw.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def run_moodboard_agent(mood: MoodObject, card: CardOutput) -> MoodboardOutput:
    try:
        profile = load_profile()
        day_number = get_day_number()

    # generate color palette
        palette_prompt = f"""
        Person's name: {profile['name']}
        Day in journey: Day {day_number} of {profile['current_phase']}
        Today's mood: {mood.primary}
        Energy: {mood.energy}
        Tone needed: {mood.tone}
        Personality traits: {', '.join(profile['personality_traits'])}

        Generate a colour palette that matches this emotional state.
        The palette caption will be their thought of the day — make it beautiful.
        """

        raw_palette = creative_llm_call(PALETTE_SYSTEM_PROMPT, palette_prompt)
        palette_dict = parse_palette_response(raw_palette)

        # fetch artwork from art institute api
        artwork_title, artwork_artist, artwork_image = fetch_artwork(mood.primary)

    # generate abstract moodboard image via FLUX
        generated_image = generate_moodboard_image(
            mood.primary,
            palette_dict["palette_caption"]
        )

        # generate artwork reflection
        reflection_prompt = f"""
        Artwork title: {artwork_title}
        Person's mood today: {mood.primary}
        Energy: {mood.energy}
        Tone: {mood.tone}
        Their hype line today was: {card.hype_line}

        Write a warm, poetic 2-3 sentence reflection on this artwork for them.
        Remember — second person, present tense, sensory language, ends with energy they deserve!!
        """

        reflection = creative_llm_call(REFLECTION_SYSTEM_PROMPT, reflection_prompt)

        return MoodboardOutput(
             palette=[ColorSwatch(**c) for c in palette_dict["palette"]],
             artwork_title=artwork_title,
             artwork_artist=artwork_artist,
             artwork_image_url=artwork_image,
             generated_image=generated_image,
             reflection=sanitize_output(reflection.strip(), "moodboard"),
             palette_caption=sanitize_output(palette_dict["palette_caption"], "moodboard")
          )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[moodboard] agent failed: {e}")
        return None