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


def save_plan(book_plan, folder_path):
    folder_path.mkdir(parents=True, exist_ok=True)
    plan_yaml = folder_path / "plan.yaml"

    with plan_yaml.open("wt", encoding="utf-8") as f_out:
        yaml.safe_dump(
            book_plan.model_dump(), f_out, allow_unicode=True, sort_keys=False
        )
    print(f"Plan saved to {plan_yaml}")
    return plan_yaml
