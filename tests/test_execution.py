import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path
import yaml
from book_generator.execute import BookExecutor, show_progress
from book_generator.models import BookPlan, BookPartPlan, BookChapterPlan, BookSectionPlan

class TestProgress(unittest.TestCase):
    # ... (TestProgress remains unchanged) ...
    def test_show_progress_start(self):
        # Test when we are at the first item
        done = []
        current = "Item 1"
        # Natural order for index-based iteration
        todo = ["Item 2", "Item 3"] 
        
        result = show_progress(done, current, todo, lambda x: x)
        
        expected = (
            "[ ] Item 1 <-- YOU'RE CURRENTLY HERE\n"
            "[ ] Item 2\n"
            "[ ] Item 3"
        )
        self.assertEqual(result, expected)

    def test_show_progress_middle(self):
        done = ["Item 1"]
        current = "Item 2"
        # Natural order
        todo = ["Item 3"]
        
        result = show_progress(done, current, todo, lambda x: x)
        
        expected = (
            "[x] Item 1\n"
            "[ ] Item 2 <-- YOU'RE CURRENTLY HERE\n"
            "[ ] Item 3"
        )
        self.assertEqual(result, expected)

    def test_show_progress_end(self):
        done = ["Item 1", "Item 2"]
        current = "Item 3"
        todo = []
        
        result = show_progress(done, current, todo, lambda x: x)
        
        expected = (
            "[x] Item 1\n"
            "[x] Item 2\n"
            "[ ] Item 3 <-- YOU'RE CURRENTLY HERE"
        )
        self.assertEqual(result, expected)

class TestExecution(unittest.TestCase):
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
                                ),
                                BookSectionPlan(
                                    name="Section 1.2",
                                    bullet_points=["P2"]
                                )
                            ]
                        ),
                        BookChapterPlan(
                            name="Chapter 2",
                            sections=[
                                BookSectionPlan(
                                    name="Section 2.1",
                                    bullet_points=["P3"]
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
    def test_execute_book_flow(self, mock_llm):
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        # Mock Writer
        mock_writer = MagicMock()
        # Default to not existing
        mock_writer.intro_exists.return_value = False
        mock_writer.section_exists.return_value = False

        # Execute
        executor = BookExecutor(self.plan, mock_writer)
        executor.execute()
        
        # Verify LLM calls
        # We expect:
        # 1. Intro Chapter 1
        # 2. Section 1.1
        # 3. Section 1.2
        # 4. Intro Chapter 2
        # 5. Section 2.1
        
        self.assertEqual(mock_llm.call_count, 5)
        
        # Verify Progress Strings in calls
        # Call 2 (Section 1.1) should have Chapter 1 as current, Chapter 2 as todo
        call_args_1_1 = mock_llm.call_args_list[1]
        prompt_1_1 = call_args_1_1.kwargs['prompt']
        
        self.assertIn("The section name: Section 1.1", prompt_1_1)
        self.assertIn("[ ] Chapter 1 <-- YOU'RE CURRENTLY HERE", prompt_1_1)
        self.assertIn("[ ] Chapter 2", prompt_1_1)
        
        # Call 3 (Section 1.2)
        call_args_1_2 = mock_llm.call_args_list[2]
        prompt_1_2 = call_args_1_2.kwargs['prompt']
        self.assertIn("The section name: Section 1.2", prompt_1_2)
        # Book progress shouldn't change (still on Chapter 1)
        self.assertIn("[ ] Chapter 1 <-- YOU'RE CURRENTLY HERE", prompt_1_2)
        
        # Chapter progress should change
        # For 1.1: Done=[], Current=1.1, Todo=[1.2]
        self.assertIn("[ ] Section 1.1 <-- YOU'RE CURRENTLY HERE", prompt_1_1)
        self.assertIn("[ ] Section 1.2", prompt_1_1)
        
        # For 1.2: Done=[1.1], Current=1.2, Todo=[]
        self.assertIn("[x] Section 1.1", prompt_1_2)
        self.assertIn("[ ] Section 1.2 <-- YOU'RE CURRENTLY HERE", prompt_1_2)
        
        # Call 5 (Section 2.1)
        call_args_2_1 = mock_llm.call_args_list[4]
        prompt_2_1 = call_args_2_1.kwargs['prompt']
        self.assertIn("The section name: Section 2.1", prompt_2_1)
        # Book progress: Ch1 done, Ch2 current
        self.assertIn("[x] Chapter 1", prompt_2_1)
        self.assertIn("[ ] Chapter 2 <-- YOU'RE CURRENTLY HERE", prompt_2_1)

        # Verify Writer Calls
        # Intro 1
        mock_writer.save_intro.assert_any_call(1, 1, "# 1. Chapter 1\n\nGenerated content")
        # Section 1.1
        mock_writer.save_section.assert_any_call(1, 1, 1, "## Section 1.1\n\nGenerated content")
        # Section 1.2
        mock_writer.save_section.assert_any_call(1, 1, 2, "## Section 1.2\n\nGenerated content")
        # Intro 2
        mock_writer.save_intro.assert_any_call(1, 2, "# 2. Chapter 2\n\nGenerated content")
        # Section 2.1
        mock_writer.save_section.assert_any_call(1, 2, 1, "## Section 2.1\n\nGenerated content")

    @patch('book_generator.execute.llm')
    def test_execute_book_skip_existing(self, mock_llm):
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "Generated content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        # Mock Writer
        mock_writer = MagicMock()
        
        # Simulate Chapter 1 Intro and Section 1.1 already exist
        def intro_exists_side_effect(part, chapter):
            return part == 1 and chapter == 1

        def section_exists_side_effect(part, chapter, section):
            return part == 1 and chapter == 1 and section == 1

        mock_writer.intro_exists.side_effect = intro_exists_side_effect
        mock_writer.section_exists.side_effect = section_exists_side_effect

        # Execute
        executor = BookExecutor(self.plan, mock_writer)
        executor.execute()
        
        # Verify LLM calls
        # Skipped: Intro 1, Section 1.1
        # Executed: Section 1.2, Intro 2, Section 2.1
        self.assertEqual(mock_llm.call_count, 3)
        
        # Verify Writer Calls
        # Should NOT call save for existing items
        # Intro 1
        with self.assertRaises(AssertionError):
            mock_writer.save_intro.assert_any_call(1, 1, unittest.mock.ANY)
        
        # Section 1.1
        with self.assertRaises(AssertionError):
            mock_writer.save_section.assert_any_call(1, 1, 1, unittest.mock.ANY)

        # Should call save for new items
        # Section 1.2
        mock_writer.save_section.assert_any_call(1, 1, 2, "## Section 1.2\n\nGenerated content")
        # Intro 2
        mock_writer.save_intro.assert_any_call(1, 2, "# 2. Chapter 2\n\nGenerated content")
        # Section 2.1
        mock_writer.save_section.assert_any_call(1, 2, 1, "## Section 2.1\n\nGenerated content")

if __name__ == '__main__':
    unittest.main()
