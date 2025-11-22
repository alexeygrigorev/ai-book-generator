import unittest
from book_generator.utils import calculate_gemini_3_cost

class TestUtils(unittest.TestCase):
    def test_cost_calculation_standard_tier(self):
        # Standard tier (< 200k tokens)
        # Input: $2.00 / 1M
        # Output: $12.00 / 1M
        
        usage = {
            'prompt_token_count': 100_000,
            'candidates_token_count': 10_000,
            'thoughts_token_count': 0
        }
        
        cost = calculate_gemini_3_cost(usage)
        
        expected_input_cost = (100_000 / 1_000_000) * 2.00
        expected_output_cost = (10_000 / 1_000_000) * 12.00
        expected_total = expected_input_cost + expected_output_cost
        
        self.assertAlmostEqual(cost, expected_total)

    def test_cost_calculation_long_context_tier(self):
        # Long context tier (> 200k tokens)
        # Input: $4.00 / 1M
        # Output: $18.00 / 1M
        
        usage = {
            'prompt_token_count': 250_000,
            'candidates_token_count': 10_000,
            'thoughts_token_count': 5_000
        }
        
        cost = calculate_gemini_3_cost(usage)
        
        expected_input_cost = (250_000 / 1_000_000) * 4.00
        total_output = 10_000 + 5_000
        expected_output_cost = (total_output / 1_000_000) * 18.00
        expected_total = expected_input_cost + expected_output_cost
        
        self.assertAlmostEqual(cost, expected_total)

    def test_cost_calculation_object_access(self):
        # Test with an object that has attributes instead of dict
        class UsageMetadata:
            def __init__(self, p, c, t):
                self.prompt_token_count = p
                self.candidates_token_count = c
                self.thoughts_token_count = t
        
        usage = UsageMetadata(1000, 100, 0)
        cost = calculate_gemini_3_cost(usage)
        self.assertGreater(cost, 0)

if __name__ == '__main__':
    unittest.main()
