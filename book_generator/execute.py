import yaml
from pathlib import Path
from typing import List, Callable, Any
from tqdm.auto import tqdm
from book_generator.models import BookPlan, ChapterSpecs, BookSectionPlan
from book_generator.utils import llm, calculate_gemini_3_cost

writer_instructions = """
Your task is based on the plan write a book section. 
You execute it section-by-section and you're given the current progress

A section should contain 800-1200 words. Don't use lists, use proper sentences,
The style is a a popular science book.

Output markdown, and use only level-3 headings. 

The output language should match the input language.
""".strip()

chapter_intro_instructions = """
Based on the chapter outline, you should write an introduction to the chapter 
describing what the chapter will cover. 

It should be 50-80 words. Don't include lists, it should be proper sentences.

The output language should match the input language.
"""

section_prompt_template = """
The chapter name: {chapter_name}

The section name: {section_name}

Outline: 

{section_outline}

Current chapter progress:

{chapter_progress}

Current book progress:

{book_progress}
""".strip()


def show_progress(
    done: List[Any], current: Any, todo: List[Any], name_function: Callable[[Any], str]
) -> str:
    """
    Generates a progress string showing completed, current, and upcoming items.

    Args:
        done: List of completed items.
        current: The item currently being processed.
        todo: List of items yet to be processed.
        name_function: Function to extract a display name from an item.

    Returns:
        A formatted string representing the progress.
    """
    progress_builder = []

    for c in done:
        line = f"[x] {name_function(c)}"
        progress_builder.append(line)

    line = f"[ ] {name_function(current)} <-- YOU'RE CURRENTLY HERE"
    progress_builder.append(line)

    for c in todo:
        line = f"[ ] {name_function(c)}"
        progress_builder.append(line)

    progress = "\n".join(progress_builder)

    return progress


class ContentWriter:
    """Abstract base class for writing book content."""

    def save_intro(self, part_number: int, chapter_number: int, content: str):
        """Saves the chapter introduction."""
        raise NotImplementedError

    def save_section(
        self, part_number: int, chapter_number: int, section_number: int, content: str
    ):
        """Saves a book section."""
        raise NotImplementedError

    def intro_exists(self, part_number: int, chapter_number: int) -> bool:
        """Checks if the chapter introduction already exists."""
        raise NotImplementedError

    def section_exists(
        self, part_number: int, chapter_number: int, section_number: int
    ) -> bool:
        """Checks if a book section already exists."""
        raise NotImplementedError


class FileSystemWriter(ContentWriter):
    """Concrete implementation of ContentWriter that saves to the file system."""

    def __init__(self, root_folder: Path):
        self.root_folder = root_folder

    def _get_intro_path(self, part_number: int, chapter_number: int) -> Path:
        return (
            self.root_folder
            / f"part_{part_number:02d}"
            / f"{chapter_number:02d}_00_intro.md"
        )

    def _get_section_path(
        self, part_number: int, chapter_number: int, section_number: int
    ) -> Path:
        return (
            self.root_folder
            / f"part_{part_number:02d}"
            / f"{chapter_number:02d}_{section_number:02d}_section.md"
        )

    def save_intro(self, part_number, chapter_number, content):
        part_folder = self.root_folder / f"part_{part_number:02d}"
        part_folder.mkdir(exist_ok=True)
        file = self._get_intro_path(part_number, chapter_number)
        file.write_text(content, encoding="utf-8")

    def save_section(self, part_number, chapter_number, section_number, content):
        part_folder = self.root_folder / f"part_{part_number:02d}"
        part_folder.mkdir(exist_ok=True)
        file = self._get_section_path(part_number, chapter_number, section_number)
        file.write_text(content, encoding="utf-8")

    def intro_exists(self, part_number, chapter_number):
        return self._get_intro_path(part_number, chapter_number).exists()

    def section_exists(self, part_number, chapter_number, section_number):
        return self._get_section_path(
            part_number, chapter_number, section_number
        ).exists()


class CostTracker:
    """Tracks the cost of LLM usage."""

    def __init__(self):
        self.total_cost = 0.0

    def update(self, usage_metadata, item_name: str):
        """Updates the total cost by calculating cost from usage_metadata."""
        report = calculate_gemini_3_cost(usage_metadata)
        self.total_cost += report.total_cost
        print(
            f"  {item_name} cost: ${report.total_cost:.6f} | Total so far: ${self.total_cost:.6f}"
        )


class BookExecutor:
    """Orchestrates the book generation process."""

    def __init__(self, book_plan: BookPlan, writer: ContentWriter):
        self.book_plan = book_plan
        self.writer = writer
        self.tracker = CostTracker()

    def process_section(
        self,
        section: BookSectionPlan,
        chapter_spec: ChapterSpecs,
        chapter_progress: str,
        book_progress: str,
    ) -> str:
        """Generates content for a single section."""
        print(f"  Writing Section: {section.name}")

        section_outline = "\n".join(section.bullet_points)

        section_prompt = section_prompt_template.format(
            chapter_name=chapter_spec.chapter.name,
            section_name=section.name,
            section_outline=section_outline,
            chapter_progress=chapter_progress,
            book_progress=book_progress,
        )

        section_response = llm(instructions=writer_instructions, prompt=section_prompt)

        self.tracker.update(section_response.usage_metadata, "Section")

        return section_response.text

    def _process_chapter_intro(self, current_spec: ChapterSpecs):
        """Generates and saves the chapter introduction."""
        if self.writer.intro_exists(
            current_spec.part_number, current_spec.chapter_number
        ):
            print(f"  Intro already exists, skipping.")
            return

        chapter_overview = yaml.safe_dump(
            current_spec.chapter.model_dump(), allow_unicode=True, sort_keys=False
        )

        intro_response = llm(
            instructions=chapter_intro_instructions, prompt=chapter_overview
        )

        self.tracker.update(intro_response.usage_metadata, "Intro")

        intro_text = intro_response.text
        intro_full_text = (
            f"# {current_spec.chapter_number}. {current_spec.chapter.name}"
            "\n\n"
            f"{intro_text}"
        ).strip()

        self.writer.save_intro(
            current_spec.part_number, current_spec.chapter_number, intro_full_text
        )

    def _process_single_section(
        self, i: int, current_spec: ChapterSpecs, book_progress: str
    ):
        """Processes a single section within a chapter."""
        current_section = current_spec.sections[i]
        section_number = i + 1

        if self.writer.section_exists(
            current_spec.part_number, current_spec.chapter_number, section_number
        ):
            print(
                f"  Section {section_number} ({current_section.name}) already exists, skipping."
            )
            return

        sections_completed = current_spec.sections[:i]
        sections_todo = current_spec.sections[i+1:]

        chapter_progress = show_progress(
            sections_completed,
            current_section,
            sections_todo,
            name_function=lambda c: c.name,
        )

        section_content = self.process_section(
            current_section, current_spec, chapter_progress, book_progress
        )

        full_section_text = (
            f"## {current_section.name}"
            "\n\n"
            f"{section_content}"
        ).strip()

        self.writer.save_section(
            current_spec.part_number,
            current_spec.chapter_number,
            section_number,
            full_section_text,
        )

    def _process_chapter_sections(
        self,
        current_spec: ChapterSpecs,
        chapters_done: List[ChapterSpecs],
        chapters_todo: List[ChapterSpecs],
    ):
        """Iterates through and processes all sections in a chapter."""
        book_progress = show_progress(
            chapters_done,
            current_spec,
            chapters_todo,
            name_function=lambda c: c.chapter.name,
        )

        for i in range(len(current_spec.sections)):
            self._process_single_section(i, current_spec, book_progress)

    def process_chapter(
        self,
        current_spec: ChapterSpecs,
        chapters_done: List[ChapterSpecs],
        chapters_todo: List[ChapterSpecs],
    ):
        """Processes an entire chapter, including introduction and sections."""
        print(
            f"Processing Chapter {current_spec.chapter_number}: {current_spec.chapter.name}"
        )
        start_cost = self.tracker.total_cost

        self._process_chapter_intro(current_spec)
        self._process_chapter_sections(current_spec, chapters_done, chapters_todo)

        chapter_cost = self.tracker.total_cost - start_cost
        print(f"Chapter {current_spec.chapter_number} cost: ${chapter_cost:.6f}")

    def _build_chapter_specs(self) -> List[ChapterSpecs]:
        """Builds a flat list of chapter specifications from the book plan."""
        chapter_specs = []
        part_idx = 0
        chapter_idx = 0

        for part in self.book_plan.parts:
            part_idx += 1
            for chapter in part.chapters:
                chapter_idx += 1
                specs = ChapterSpecs(
                    part=part,
                    part_number=part_idx,
                    chapter=chapter,
                    chapter_number=chapter_idx,
                    sections=chapter.sections,
                )
                chapter_specs.append(specs)
        return chapter_specs

    def _process_all_chapters(self, chapter_specs: List[ChapterSpecs]):
        """Iterates through and processes all chapters."""
        print(f"Total chapters to write: {len(chapter_specs)}")

        for i, current_spec in enumerate(chapter_specs):
            chapters_done = chapter_specs[:i]
            chapters_todo = chapter_specs[i + 1 :]

            self.process_chapter(current_spec, chapters_done, chapters_todo)
            print(f"Chapter {current_spec.chapter_number} completed.")

    def execute(self):
        """Executes the entire book generation plan."""
        chapter_specs = self._build_chapter_specs()
        self._process_all_chapters(chapter_specs)
        print(f"Execution completed. Total Cost: ${self.tracker.total_cost:.6f}")


def execute_plan(folder: str):
    root_folder = Path("books") / folder
    plan_yaml = root_folder / "plan.yaml"

    if not plan_yaml.exists():
        print(f"Plan file not found at {plan_yaml}. Please run plan.py first.")
        return

    print(f"Loading plan from {plan_yaml}...")
    with plan_yaml.open("rt", encoding="utf-8") as f_in:
        data = yaml.safe_load(f_in)
        book_plan = BookPlan.model_validate(data)

    writer = FileSystemWriter(root_folder)
    executor = BookExecutor(book_plan, writer)
    executor.execute()


if __name__ == "__main__":
    execute_plan("sirens")
