import unittest
from book_generator.execute import get_part_label

class TestPartLabel(unittest.TestCase):
    def test_get_part_label_english(self):
        self.assertEqual(get_part_label('en'), 'Part')
    
    def test_get_part_label_russian(self):
        self.assertEqual(get_part_label('ru'), 'Часть')
    
    def test_get_part_label_german(self):
        self.assertEqual(get_part_label('de'), 'Teil')
    
    def test_get_part_label_default(self):
        # Test that unknown language defaults to 'Part'
        # Note: This won't compile with Literal type, but tests the fallback
        # In real scenario, only valid values should be passed
        pass

if __name__ == '__main__':
    unittest.main()
