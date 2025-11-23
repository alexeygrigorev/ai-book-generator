import unittest
import yaml
from pathlib import Path
from book_generator.models import BookPlan

class TestModels(unittest.TestCase):
    def test_load_plan_yaml(self):
        # Path to the existing plan.yaml
        plan_path = Path('books/sirens/plan.yaml')

        with plan_path.open('rt', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Validate against the model
        book_plan = BookPlan.model_validate(data)
        
        self.assertIsInstance(book_plan, BookPlan)
        self.assertTrue(len(book_plan.parts) > 0)
        self.assertTrue(len(book_plan.parts[0].chapters) > 0)
        self.assertTrue(len(book_plan.parts[0].chapters[0].sections) > 0)
        
        print(f"Successfully validated plan: {book_plan.name}")

if __name__ == '__main__':
    unittest.main()
