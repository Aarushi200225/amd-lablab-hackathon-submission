import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import gradio as gr
from core.profile import setup_database, save_profile, profile_exists, load_profile
from core.orchestrator import run_daily_card
from core.memory import update_journal_note

setup_database()


# ── Onboarding ──────────────────────────────────────────────────────────

def handle_onboarding(
    name, disorder_category,
    trigger_foods, safe_foods,
    challenge_foods, comfort_foods,
    personality_traits, health_context,
    current_phase
):
    if not name or not safe_foods:
        return "Please enter your name and at least one safe food."

    save_profile({
        "name": name,
        "disorder_category": disorder_category,
        "trigger_foods": [f.strip() for f in trigger_foods.split(",") if f.strip()],
        "safe_foods": [f.strip() for f in safe_foods.split(",") if f.strip()],
        "challenge_foods": [f.strip() for f in challenge_foods.split(",") if f.strip()],
        "comfort_foods": [f.strip() for f in comfort_foods.split(",") if f.strip()],
        "personality_traits": personality_traits,
        "health_context": health_context,
        "current_phase": int(current_phase.replace("-day plan", ""))
    })

    return "You're all set! Click the 'My daily card' tab above to begin 💙"


# ── Daily Card ──────────────────────────────────────────────────────────

def handle_daily_card(mood_input):
    if not mood_input.strip():
        return ["Just type anything — even one word works."] + [None] * 12

    try:
        result = run_daily_card(mood_input)

        card = result["card"]
        meal = result["meal"]
        board = result["moodboard"]
        progress = result["progress"]
        mood = result["mood"]

        card_text = ('### ' + card.hype_line + '\n\n*' + card.micro_prompt + '*\n\n' + card.day_marker) if card else 'Card unavailable'
        mood_text = f"Today s vibe — **{mood.primary}** · energy **{mood.energy}**" if mood else ""

        meal_image = meal.recipe_image if meal else None
        meal_text = ('**' + meal.dish_name + '**\n\n' + meal.description + '\n\n_' + meal.why_today + '_') if meal else 'Meal unavailable'
        sensory_text = meal.sensory_note if meal else ""
        ingredients_text = f"What s in it: {', '.join(meal.ingredients_preview)}" if meal and meal.ingredients_preview else ""
        social_text = meal.social_nudge if meal else ""

        if board:
            palette_text = "\n".join([s.hex + " — " + s.name for s in board.palette])
            palette_caption = f"✨ {board.palette_caption}"
            artwork_image = board.artwork_image_url
            sd_image = board.generated_image
            reflection_text = "*" + board.artwork_title + "*\n\n" + board.reflection
        else:
            palette_text = "Palette unavailable"
            palette_caption = ""
            artwork_image = None
            sd_image = None
            reflection_text = ""

        progress_text = progress.progress_note if progress else ""

        return [
            card_text, mood_text,
            meal_image, meal_text,
            sensory_text, ingredients_text, social_text,
            palette_text, palette_caption,
            artwork_image, sd_image, reflection_text,
            progress_text
        ]

    except Exception as e:
        import traceback
        traceback.print_exc()
        return [f"Error: {str(e)}"] + [None] * 12

def handle_journal(journal_note):
    if journal_note.strip():
        update_journal_note(journal_note.strip())
        return "Saved. 💙"
    return ""


# ── Gradio UI ───────────────────────────────────────────────────────────

with gr.Blocks(title="Nourish") as app:

    with gr.Tabs() as tabs:

        # ── Tab 1: Onboarding ───────────────────────────────────────
        with gr.Tab("Getting started", id=0):
            gr.Markdown("# Welcome to Nourish!")
            gr.Markdown("Fill this in once to get started.")

            name = gr.Textbox(label="What would you like us to call you?")
            disorder_category = gr.Dropdown(
                choices=["Anorexia Nervosa", "Bulimia Nervosa",
                         "ARFID", "BED", "Other / Prefer not to say"],
                label="Which best describes your experience?"
            )
            gr.Markdown("### Your food world")
            gr.Markdown("Separate each item with a comma.")
            trigger_foods = gr.Textbox(label="Foods that feel unsafe or triggering")
            safe_foods = gr.Textbox(label="Foods that feel okay and comfortable")
            challenge_foods = gr.Textbox(label="Foods you want to work toward")
            comfort_foods = gr.Textbox(label="Foods that feel grounding or warm")
            gr.Markdown("### A little about you")
            personality_traits = gr.CheckboxGroup(
                choices=["Anxious", "Perfectionist", "Avoidant", "Sensitive",
                         "Creative", "Introverted", "Determined",
                         "Overthinking", "Gentle with myself"],
                label="How would you describe yourself?"
            )
            health_context = gr.Textbox(
                label="Anything else we should know?",
                placeholder="e.g. mornings are hardest for me"
            )
            current_phase = gr.Dropdown(
                choices=["30-day plan", "60-day plan", "90-day plan"],
                label="Which plan are you starting with?"
            )
            onboard_btn = gr.Button("Start my journey", variant="primary")
            onboard_status = gr.Markdown()

        # ── Tab 2: Daily Card ───────────────────────────────────────
        with gr.Tab("My daily card", id=1):
            gr.Markdown("# Hey there 💙")
            gr.Markdown("How are you feeling today?")

            mood_input = gr.Textbox(
                placeholder="tired, okay, anxious, good... anything works",
                label=""
            )
            generate_btn = gr.Button("Generate my daily card", variant="primary")

            gr.Markdown("---")
            card_output = gr.Markdown()
            mood_output = gr.Markdown()

            gr.Markdown("---")
            meal_image_output = gr.Image(label="Today's dish")
            meal_output = gr.Markdown()
            sensory_output = gr.Markdown()
            ingredients_output = gr.Markdown()
            social_output = gr.Markdown()

            gr.Markdown("---")
            gr.Markdown("### Today's palette")
            palette_output = gr.Markdown()
            palette_caption_output = gr.Markdown()

            gr.Markdown("### Today's artwork")
            artwork_image_output = gr.Image(label="Artwork")
            sd_image_output = gr.Image(label="Your generated moodboard")
            reflection_output = gr.Markdown()

            gr.Markdown("---")
            gr.Markdown("### How far you've come")
            progress_output = gr.Markdown()

            gr.Markdown("---")
            journal_input = gr.Textbox(
                placeholder="How did today feel? No pressure — this is just for you.",
                label="Anything you want to add?"
            )
            journal_btn = gr.Button("Save note")
            journal_status = gr.Markdown()

            gr.Markdown("---")
            gr.Markdown(
                "💙 Nourish is a creative companion, not medical advice. "
                "Always work with your care team."
            )

    # ── Button handlers ─────────────────────────────────────────────
    onboard_btn.click(
        handle_onboarding,
        inputs=[
            name, disorder_category,
            trigger_foods, safe_foods,
            challenge_foods, comfort_foods,
            personality_traits, health_context,
            current_phase
        ],
        outputs=onboard_status
    )

    generate_btn.click(
        handle_daily_card,
        inputs=[mood_input],
        outputs=[
            card_output, mood_output,
            meal_image_output, meal_output,
            sensory_output, ingredients_output, social_output,
            palette_output, palette_caption_output,
            artwork_image_output, sd_image_output, reflection_output,
            progress_output
        ]
    )

    journal_btn.click(
        handle_journal,
        inputs=[journal_input],
        outputs=[journal_status]
    )

if __name__ == "__main__":
    app.launch(
        share=True,
        server_name="0.0.0.0",
        allowed_paths=["/shared-docker/Nourish/nourish/data/generated_images"]
    )