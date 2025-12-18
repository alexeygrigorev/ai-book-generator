import argparse
from pathlib import Path

import yaml

from google.genai import types
from book_generator.models import BookPlan
from book_generator.utils import get_client, calculate_gemini_3_cost

planner_instructions = """
Your role is planning the book. 

You're given a conversation beween a user and an assistant about a book. Based 
on the conversation, you need to create a detailed book plan with each chapter
and section. Later we will give this to the writer, who will actually write the book.

A chapter should have at least 4 sections, and each section should have at least 7-8 bullet
points. 

Often the input doesn't contain all the information you need, so you must use your knowledge
to make sure the output is comprehensive.

The language of the output should match the language of the input.

Do not add numbers to chapter and section names. It will be added later automatically.

IMPORTANT: Generate a 'slug' field that is a filesystem-safe version of the book name (lowercase, hyphens instead of spaces, max 50 chars, no special characters except hyphens).
"""


def generate_text_plan_stream(topic: str, size: str):
    """Generate initial book plan as streaming text."""
    instructions = "You are a book planning assistant. Create detailed, comprehensive book outlines."
    prompt = f"""Create a detailed book plan for the following:

Topic: {topic}
Size: {size}

Please provide a comprehensive book outline including parts (if applicable), chapters, and sections with brief descriptions."""

    client = get_client()
    response = client.models.generate_content_stream(
        model="models/gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            system_instruction=instructions,
        ),
        contents=prompt,
    )

    full_text = ""
    last_chunk = None
    for chunk in response:
        last_chunk = chunk
        if chunk.text:
            full_text += chunk.text
            yield chunk.text

    # Get usage from the last chunk
    if last_chunk and hasattr(last_chunk, "usage_metadata"):
        cost_report = calculate_gemini_3_cost(last_chunk.usage_metadata)
        yield ("__DONE__", full_text, cost_report.total_cost)
    else:
        # Fallback if no usage metadata
        yield ("__DONE__", full_text, 0.0)


def refine_text_plan_stream(current_plan: str, feedback: str):
    """Refine text plan based on feedback with streaming."""
    instructions = "You are a book planning assistant. Update the book outline based on user feedback."
    prompt = f"""Current plan:

{current_plan}

User request: {feedback}

Please provide the updated plan."""

    client = get_client()
    response = client.models.generate_content_stream(
        model="models/gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            system_instruction=instructions,
        ),
        contents=prompt,
    )

    full_text = ""
    last_chunk = None
    for chunk in response:
        last_chunk = chunk
        if chunk.text:
            full_text += chunk.text
            yield chunk.text

    # Get usage from the last chunk
    if last_chunk and hasattr(last_chunk, "usage_metadata"):
        cost_report = calculate_gemini_3_cost(last_chunk.usage_metadata)
        yield ("__DONE__", full_text, cost_report.total_cost)
    else:
        # Fallback if no usage metadata
        yield ("__DONE__", full_text, 0.0)


def create_book_plan(prompt):
    """Create structured book plan from text."""
    print("Generating book plan...")
    client = get_client()
    plan_response = client.models.generate_content(
        model="models/gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            system_instruction=planner_instructions,
            response_mime_type="application/json",
            response_json_schema=BookPlan.model_json_schema(),
        ),
        contents=prompt,
    )

    calculate_gemini_3_cost(plan_response.usage_metadata, print_cost=True)
    book_plan = BookPlan.model_validate(plan_response.parsed)
    cost_report = calculate_gemini_3_cost(plan_response.usage_metadata)
    return book_plan, cost_report.total_cost


def save_plan(book_plan, destination):
    """
    Save the book plan to YAML. Destination can be a directory or a file path.
    """
    destination_path = Path(destination)
    if destination_path.suffix:
        folder_path = destination_path.parent
        plan_yaml = destination_path
    else:
        folder_path = destination_path
        plan_yaml = folder_path / "plan.yaml"

    folder_path.mkdir(parents=True, exist_ok=True)

    with plan_yaml.open("wt", encoding="utf-8") as f_out:
        yaml.safe_dump(
            book_plan.model_dump(), f_out, allow_unicode=True, sort_keys=False
        )
    print(f"Plan saved to {plan_yaml}")
    return plan_yaml


def main():
    """
    uv run python -m book_generator.plan \
      --prompt-file books/fireworks-ru/input.txt \
      --output books/fireworks-ru/plan.yaml
    """
    parser = argparse.ArgumentParser(
        description="Generate a structured book plan from a prompt file."
    )
    parser.add_argument(
        "-p",
        "--prompt-file",
        required=True,
        type=Path,
        help="Path to a text file containing the plan prompt/conversation.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Path to save the plan. Can be a directory or a file path. "
            "Defaults to books/<slug>/plan.yaml."
        ),
    )
    args = parser.parse_args()

    prompt_text = args.prompt_file.read_text(encoding="utf-8")
    book_plan, total_cost = create_book_plan(prompt_text)

    destination = args.output if args.output else Path("books") / book_plan.slug
    plan_path = save_plan(book_plan, destination)

    print(f"Total cost: ${total_cost:.6f}")
    print(f"Plan written to {plan_path}")


if __name__ == "__main__":
    main()
