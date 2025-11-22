from dataclasses import dataclass

from google import genai
from google.genai import types


# Initialize the client
_client = None

def get_client():
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


@dataclass
class CostReport:
    total_cost: float
    input_cost: float
    output_cost: float
    prompt_tokens: int
    output_tokens: int
    tier_name: str

def calculate_gemini_3_cost(usage_metadata, print_cost=False) -> CostReport:
    """
    Calculates cost for Gemini 3 Pro Preview based on usage_metadata object.
    Automatically handles the pricing tiers for prompts above/below 200k tokens.
    """

    # 1. Safely extract token counts (handling both object attributes and dict keys)
    def get_val(data, attr):
        return getattr(data, attr, data.get(attr, 0)) if hasattr(data, 'get') else getattr(data, attr, 0)

    prompt_tokens = get_val(usage_metadata, 'prompt_token_count')
    candidates_tokens = get_val(usage_metadata, 'candidates_token_count')
    # Use 0 if thoughts_token_count is missing (backward compatibility)
    thoughts_tokens = get_val(usage_metadata, 'thoughts_token_count') 

    # 2. Determine Pricing Tier (Nov 2025 Rates)
    # If prompt is > 200k, rates increase for both input and output
    if prompt_tokens > 200_000:
        input_rate = 4.00
        output_rate = 18.00
        tier_name = "Long Context (>200k)"
    else:
        input_rate = 2.00
        output_rate = 12.00
        tier_name = "Standard (<200k)"

    # 3. Calculate Costs
    # Thoughts are billed as output tokens
    total_output_tokens = candidates_tokens + thoughts_tokens

    input_cost = (prompt_tokens / 1_000_000) * input_rate
    output_cost = (total_output_tokens / 1_000_000) * output_rate
    total_cost = input_cost + output_cost

    if print_cost:
        # 4. Print Report
        print(f"--- Gemini 3 Pro Cost Report ---")
        print(f"Tier:            {tier_name}")
        print(f"Prompt Tokens:   {prompt_tokens:,}  (@ ${input_rate}/1M)")
        print(f"Output Tokens:   {total_output_tokens:,}  (@ ${output_rate}/1M)")
        print(f"  - Candidates:  {candidates_tokens:,}")
        print(f"  - Thoughts:    {thoughts_tokens:,}")
        print(f"--------------------------------")
        print(f"Input Cost:      ${input_cost:.6f}")
        print(f"Output Cost:     ${output_cost:.6f}")
        print(f"TOTAL COST:      ${total_cost:.6f}")

    return CostReport(
        total_cost=total_cost,
        input_cost=input_cost,
        output_cost=output_cost,
        prompt_tokens=prompt_tokens,
        output_tokens=total_output_tokens,
        tier_name=tier_name
    )

def llm(instructions, prompt, model="models/gemini-3-pro-preview"):
    client = get_client()
    response = client.models.generate_content(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=instructions,
        ),
        contents=prompt
    )
    return response
