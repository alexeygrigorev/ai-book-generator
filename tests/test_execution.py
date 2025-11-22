import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path
import yaml
from book_generator.execute import BookExecutor, show_progress
from book_generator.models import BookPlan, BookPartPlan, BookChapterPlan, BookSectionPlan
from book_generator.execute import ChapterSpecs


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

    @patch('book_generator.execute.llm')
    def test_process_chapter_intro(self, mock_llm):
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "Intro content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.intro_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)
        
        # Create a real spec
        chapter_plan = BookChapterPlan(
            name="Chapter 1",
            sections=[]
        )
        # We need a dummy part plan for ChapterSpecs, but it's not used in this method directly except for part_number
        # ChapterSpecs requires: part, part_number, chapter, chapter_number, sections
        
        # We can use self.plan from setUp which has populated parts
        part_plan = self.plan.parts[0]
        
        
        chapter_spec = ChapterSpecs(
            part=part_plan,
            part_number=1,
            chapter=chapter_plan,
            chapter_number=1,
            sections=[]
        )

        executor._process_chapter_intro(chapter_spec)

        self.assertEqual(mock_llm.call_count, 1)
        mock_writer.save_intro.assert_called_once()
        self.assertGreater(executor.tracker.total_cost, 0)

    @patch('book_generator.execute.llm')
    def test_process_single_section(self, mock_llm):
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "Section content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.section_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)

        # Create a real spec with 2 sections
        s1 = BookSectionPlan(name="S1", bullet_points=["b1"])
        s2 = BookSectionPlan(name="S2", bullet_points=["b2"])
        
        chapter_plan = BookChapterPlan(
            name="Chapter 1",
            sections=[s1, s2]
        )
        
        part_plan = self.plan.parts[0]
        
        from book_generator.execute import ChapterSpecs

        chapter_spec = ChapterSpecs(
            part=part_plan,
            part_number=1,
            chapter=chapter_plan,
            chapter_number=1,
            sections=[s1, s2]
        )

        # Test processing the first section
        executor._process_single_section(0, chapter_spec, "Book Progress")

        self.assertEqual(mock_llm.call_count, 1)
        mock_writer.save_section.assert_called_once()
        self.assertGreater(executor.tracker.total_cost, 0)

    @patch('book_generator.execute.llm')
    def test_process_chapter_sections(self, mock_llm):
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "Section content"
        mock_response.usage_metadata = {'prompt_token_count': 10, 'candidates_token_count': 10}
        mock_llm.return_value = mock_response

        mock_writer = MagicMock()
        mock_writer.section_exists.return_value = False

        executor = BookExecutor(self.plan, mock_writer)

        # Create a real spec with 2 sections
        s1 = BookSectionPlan(name="S1", bullet_points=["b1"])
        s2 = BookSectionPlan(name="S2", bullet_points=["b2"])
        
        chapter_plan = BookChapterPlan(
            name="Chapter 1",
            sections=[s1, s2]
        )
        
        part_plan = self.plan.parts[0]
        
        from book_generator.execute import ChapterSpecs

        chapter_spec = ChapterSpecs(
            part=part_plan,
            part_number=1,
            chapter=chapter_plan,
            chapter_number=1,
            sections=[s1, s2]
        )

        executor._process_chapter_sections(chapter_spec, [], [])

        # _process_chapter_sections calls _process_single_section twice
        # Each call invokes LLM and saves section
        self.assertEqual(mock_llm.call_count, 2)
        self.assertEqual(mock_writer.save_section.call_count, 2)
        self.assertGreater(executor.tracker.total_cost, 0)

    def test_build_chapter_specs(self):
        mock_writer = MagicMock()
        executor = BookExecutor(self.plan, mock_writer)
        
        specs = executor._build_chapter_specs()
        
        # Plan has 2 chapters (Chapter 1 in Part 1, Chapter 2 in Part 1)
        self.assertEqual(len(specs), 2)
        
        self.assertEqual(specs[0].chapter.name, "Chapter 1")
        self.assertEqual(specs[0].chapter_number, 1)
        self.assertEqual(specs[0].part_number, 1)
        
        self.assertEqual(specs[1].chapter.name, "Chapter 2")
        self.assertEqual(specs[1].chapter_number, 2)
        self.assertEqual(specs[1].part_number, 1)

    def test_process_all_chapters(self):
        mock_writer = MagicMock()
        executor = BookExecutor(self.plan, mock_writer)
        
        # Mock process_chapter to verify calls
        executor.process_chapter = MagicMock()
        
        specs = executor._build_chapter_specs()
        executor._process_all_chapters(specs)
        
        self.assertEqual(executor.process_chapter.call_count, 2)
        
        # Verify arguments for first call
        args, _ = executor.process_chapter.call_args_list[0]
        current_spec, done, todo = args
        self.assertEqual(current_spec.chapter.name, "Chapter 1")
        self.assertEqual(len(done), 0)
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo[0].chapter.name, "Chapter 2")

        # Verify arguments for second call
        args, _ = executor.process_chapter.call_args_list[1]
        current_spec, done, todo = args
        self.assertEqual(current_spec.chapter.name, "Chapter 2")
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0].chapter.name, "Chapter 1")
        self.assertEqual(len(todo), 0)

if __name__ == '__main__':
    unittest.main()
