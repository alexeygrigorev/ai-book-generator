import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil
from book_generator.execute import BookExecutor, FileSystemWriter
from book_generator.models import BookPlan, BookPartPlan, BookChapterPlan, BookSectionPlan

class TestExecutorOutput(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.root_folder = Path(self.test_dir) / 'test_book'
        self.root_folder.mkdir()
        
        self.plan = BookPlan(
            book_language="en",
            name="Test Book",
            target_reader="Testers",
            back_cover_description="A compelling back cover description.",
            parts=[
                BookPartPlan(
                    name="Part 1",
                    introduction="Introduction to Part 1.",
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
                ),
                BookPartPlan(
                    name="Part 2",
                    introduction="Introduction to Part 2.",
                    chapters=[]
                )
            ]
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_filesystem_writer_back_cover(self):
        writer = FileSystemWriter(self.root_folder)
        content = "Back cover content"
        writer.save_back_cover(content)
        
        expected_path = self.root_folder / "back_cover.md"
        self.assertTrue(expected_path.exists())
        self.assertEqual(expected_path.read_text(encoding="utf-8"), content)
        self.assertTrue(writer.back_cover_exists())

    def test_filesystem_writer_part_intro(self):
        writer = FileSystemWriter(self.root_folder)
        content = "Part 1 Intro"
        writer.save_part_intro(1, content)
        
        expected_path = self.root_folder / "part_01" / "_part_intro.md"
        self.assertTrue(expected_path.exists())
        self.assertEqual(expected_path.read_text(encoding="utf-8"), content)
        self.assertTrue(writer.part_intro_exists(1))

    @patch('book_generator.execute.llm')
    def test_execute_saves_back_cover(self, mock_llm):
        # Mock LLM to avoid actual calls
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.back_cover_exists.return_value = False
        mock_writer.part_intro_exists.return_value = False
        mock_writer.intro_exists.return_value = False
        mock_writer.section_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)
        executor.execute()

        mock_writer.save_back_cover.assert_called_once_with("A compelling back cover description.")

    @patch('book_generator.execute.llm')
    def test_execute_saves_part_intros(self, mock_llm):
        # Mock LLM
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.back_cover_exists.return_value = False
        mock_writer.part_intro_exists.return_value = False
        mock_writer.intro_exists.return_value = False
        mock_writer.section_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)
        executor.execute()

        # Check Part 1
        expected_content_1 = "# Part 1: Part 1\n\nIntroduction to Part 1."
        mock_writer.save_part_intro.assert_any_call(1, expected_content_1)

        # Check Part 2
        expected_content_2 = "# Part 2: Part 2\n\nIntroduction to Part 2."
        mock_writer.save_part_intro.assert_any_call(2, expected_content_2)

    @patch('book_generator.execute.llm')
    def test_execute_skips_existing_back_cover(self, mock_llm):
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.back_cover_exists.return_value = True
        mock_writer.part_intro_exists.return_value = False
        mock_writer.intro_exists.return_value = False
        mock_writer.section_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)
        executor.execute()

        mock_writer.save_back_cover.assert_not_called()

    @patch('book_generator.execute.llm')
    def test_execute_skips_existing_part_intros(self, mock_llm):
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.back_cover_exists.return_value = False
        mock_writer.part_intro_exists.return_value = True # All exist
        mock_writer.intro_exists.return_value = False
        mock_writer.section_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)
        executor.execute()

        mock_writer.save_part_intro.assert_not_called()

    @patch('book_generator.execute.llm')
    def test_execute_saves_russian_part_intros(self, mock_llm):
        # Test that Russian books use Russian part labels
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        # Create a Russian book plan
        russian_plan = BookPlan(
            book_language='ru',
            name="Тестовая книга",
            target_reader="Тестеры",
            back_cover_description="Описание книги",
            parts=[
                BookPartPlan(
                    name="Первая часть",
                    introduction="Введение в первую часть.",
                    chapters=[]
                )
            ]
        )

        mock_writer = MagicMock()
        mock_writer.back_cover_exists.return_value = False
        mock_writer.part_intro_exists.return_value = False

        executor = BookExecutor(russian_plan, mock_writer)
        executor.execute()

        # Check that Russian label "Часть" is used
        expected_content = "# Часть 1: Первая часть\n\nВведение в первую часть."
        mock_writer.save_part_intro.assert_called_once_with(1, expected_content)

if __name__ == '__main__':
    unittest.main()
