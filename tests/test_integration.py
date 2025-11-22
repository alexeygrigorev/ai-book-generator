import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path
from book_generator.execute import BookExecutor, FileSystemWriter
from book_generator.models import BookPlan, BookPartPlan, BookChapterPlan, BookSectionPlan

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.root_folder = Path(self.test_dir) / 'sirens'
        self.root_folder.mkdir()
        
        self.plan = BookPlan(
            name="Test Book",
            target_reader="Testers",
            back_cover_description="A test book.",
            parts=[
                BookPartPlan(
                    name="Part 1",
                    introduction="Intro 1",
                    chapters=[
                        BookChapterPlan(
                            name="Chapter 1",
                            sections=[
                                BookSectionPlan(
                                    name="Section 1.1",
                                    bullet_points=["P1"]
                                )
                            ]
                        )
                    ]
                )
            ]
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('book_generator.execute.llm')
    def test_execute_book_integration(self, mock_llm):
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        # Use real FileSystemWriter
        writer = FileSystemWriter(self.root_folder)

        # Execute
        executor = BookExecutor(self.plan, writer)
        executor.execute()
        
        # Verify files exist and have content
        intro_file = self.root_folder / 'part_01/01_00_intro.md'
        self.assertTrue(intro_file.exists())
        self.assertIn("Generated content", intro_file.read_text(encoding='utf-8'))

        section_file = self.root_folder / 'part_01/01_01_section.md'
        self.assertTrue(section_file.exists())
        self.assertIn("Generated content", section_file.read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()
