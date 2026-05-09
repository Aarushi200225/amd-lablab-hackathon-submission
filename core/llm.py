import torch
from transformers import pipeline
from dotenv import load_dotenv

load_dotenv('x.env')

# confirm GPU is available
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[llm] running on: {DEVICE}")

# load Qwen once at module level — avoids reloading on every call
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
CREATIVE_MODEL = "Qwen/Qwen2.5-7B-Instruct"

print(f"[llm] loading {DEFAULT_MODEL}...")

_pipeline = pipeline(
    "text-generation",
    model=DEFAULT_MODEL,
    torch_dtype=torch.float16,
    device_map="auto"
)

print("[llm] model loaded successfully")


def llm_call(system_prompt: str, user_prompt: str, model: str = None) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    output = _pipeline(
        messages,
        max_new_tokens=512,
        temperature=0.7,
        do_sample=True
    )

    # extract generated text from output
    return output[0]["generated_text"][-1]["content"].strip()
    # free unused GPU memory after each call
    torch.cuda.empty_cache()


def creative_llm_call(system_prompt: str, user_prompt: str) -> str:
    # same model, slightly higher temperature for creative tasks
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    output = _pipeline(
        messages,
        max_new_tokens=512,
        temperature=0.9,
        do_sample=True
    )

    return output[0]["generated_text"][-1]["content"].strip()
    # free unused GPU memory after each call
    torch.cuda.empty_cache()