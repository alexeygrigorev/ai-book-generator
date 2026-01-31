import sys
import yaml
from pathlib import Path
from typing import List, Callable, Any, Literal, Optional

import questionary

from chapter_based.models import BookPlan, ChapterSpecs
from book_generator.utils import llm, calculate_gemini_3_cost


def get_part_label(language: Literal["ru", "en", "de"]) -> str:
    """Returns the localized label for 'Part' based on the book language.

    Args:
        language: The book language code ('ru', 'en', or 'de')

    Returns:
        The localized word for 'Part' in the specified language
    """
    labels = {
        "en": "Part",
        "ru": "Часть",
        "de": "Teil",
    }
    return labels.get(language, "Part")


writer_instructions = """
Your task is to write a complete chapter based on the given outline.

You should write a comprehensive chapter that covers all the bullet points provided.
A chapter should contain approximately 3000-5000 words.

The style should be that of a popular science book - engaging, informative, and accessible.

Output markdown, and use level-2 (##) and level-3 (###) headings for sections within the chapter.
Do not use level-1 headings as the chapter title will be added automatically.

The output language should match the input language.
""".strip()


chapter_prompt_template = """
The book title: {book_title}

The chapter name: {chapter_name}

Chapter outline (bullet points to cover):

{chapter_outline}

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


def list_available_plan_folders() -> List[Path]:
    """Returns plan folders under books/ that have chapter-based plans."""
    books_root = Path("books")
    if not books_root.exists():
        return []

    available = []
    for folder in sorted(books_root.iterdir()):
        if not folder.is_dir():
            continue

        plan_file = folder / "plan.yaml"
        ready_flag = folder / "_ready"

        if ready_flag.exists():
            continue

        if plan_file.exists():
            # Check if it's a chapter-based plan (no sections in chapters)
            with plan_file.open("rt", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                # Chapter-based plans have "bullet_points" directly in chapters
                is_chapter_based = False
                for part in data.get("parts", []):
                    for chapter in part.get("chapters", []):
                        if "bullet_points" in chapter:
                            is_chapter_based = True
                            break
                if is_chapter_based:
                    available.append(folder)

    return available


def prompt_for_plan_selection(plan_folders: List[Path]) -> Optional[str]:
    """Prompts the user to select a plan folder using Questionary if available."""
    if not plan_folders:
        print("No available chapter-based plans found in books/.")
        return None

    choice = questionary.select(
        "Select a chapter-based plan to execute",
        choices=[
            questionary.Choice(title=folder.name, value=folder.name)
            for folder in plan_folders
        ],
        default=plan_folders[0].name,
    ).ask()

    return choice


class ContentWriter:
    """Abstract base class for writing book content."""

    def save_chapter(self, part_number: int, chapter_number: int, content: str):
        """Saves a full chapter."""
        raise NotImplementedError

    def save_part_intro(self, part_number: int, content: str):
        """Saves the part introduction."""
        raise NotImplementedError

    def save_back_cover(self, content: str):
        """Saves the back cover description."""
        raise NotImplementedError

    def chapter_exists(self, part_number: int, chapter_number: int) -> bool:
        """Checks if a chapter already exists."""
        raise NotImplementedError

    def part_intro_exists(self, part_number: int) -> bool:
        """Checks if the part introduction already exists."""
        raise NotImplementedError

    def back_cover_exists(self) -> bool:
        """Checks if the back cover description already exists."""
        raise NotImplementedError


class FileSystemWriter(ContentWriter):
    """Concrete implementation of ContentWriter that saves to the file system."""

    def __init__(self, root_folder: Path):
        self.root_folder = root_folder

    def _get_chapter_path(self, part_number: int, chapter_number: int) -> Path:
        return (
            self.root_folder
            / f"part_{part_number:02d}"
            / f"{chapter_number:02d}_chapter.md"
        )

    def _get_part_intro_path(self, part_number: int) -> Path:
        return (
            self.root_folder
            / f"part_{part_number:02d}"
            / f"_part_{part_number:02d}_intro.md"
        )

    def _get_back_cover_path(self) -> Path:
        return self.root_folder / "back_cover.md"

    def save_chapter(self, part_number, chapter_number, content):
        part_folder = self.root_folder / f"part_{part_number:02d}"
        part_folder.mkdir(exist_ok=True)
        file = self._get_chapter_path(part_number, chapter_number)
        file.write_text(content, encoding="utf-8")

    def save_part_intro(self, part_number, content):
        part_folder = self.root_folder / f"part_{part_number:02d}"
        part_folder.mkdir(exist_ok=True)
        file = self._get_part_intro_path(part_number)
        file.write_text(content, encoding="utf-8")

    def save_back_cover(self, content):
        file = self._get_back_cover_path()
        file.write_text(content, encoding="utf-8")

    def chapter_exists(self, part_number, chapter_number):
        return self._get_chapter_path(part_number, chapter_number).exists()

    def part_intro_exists(self, part_number):
        return self._get_part_intro_path(part_number).exists()

    def back_cover_exists(self):
        return self._get_back_cover_path().exists()


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
    """Orchestrates the chapter-based book generation process."""

    def __init__(self, book_plan: BookPlan, writer: ContentWriter):
        self.book_plan = book_plan
        self.writer = writer
        self.tracker = CostTracker()

    def process_chapter(
        self,
        chapter_spec: ChapterSpecs,
        book_progress: str,
    ) -> str:
        """Generates content for a full chapter."""
        print(f"  Writing Chapter: {chapter_spec.chapter.name}")

        chapter_outline = "\n".join(f"- {bp}" for bp in chapter_spec.chapter.bullet_points)

        chapter_prompt = chapter_prompt_template.format(
            book_title=self.book_plan.name,
            chapter_name=chapter_spec.chapter.name,
            chapter_outline=chapter_outline,
            book_progress=book_progress,
        )

        chapter_response = llm(instructions=writer_instructions, prompt=chapter_prompt)

        self.tracker.update(chapter_response.usage_metadata, "Chapter")

        # Add chapter title as level-1 heading
        chapter_content = f"# {chapter_spec.chapter_number}. {chapter_spec.chapter.name}\n\n{chapter_response.text}"

        return chapter_content

    def _process_single_chapter(
        self, i: int, chapter_specs: List[ChapterSpecs], book_progress: str
    ):
        """Processes a single chapter."""
        current_spec = chapter_specs[i]

        if self.writer.chapter_exists(
            current_spec.part_number, current_spec.chapter_number
        ):
            print(
                f"  Chapter {current_spec.chapter_number} ({current_spec.chapter.name}) already exists, skipping."
            )
            return

        chapter_content = self.process_chapter(current_spec, book_progress)

        self.writer.save_chapter(
            current_spec.part_number,
            current_spec.chapter_number,
            chapter_content,
        )

    def _process_all_chapters(self, chapter_specs: List[ChapterSpecs]):
        """Iterates through and processes all chapters."""
        print(f"Total chapters to write: {len(chapter_specs)}")

        for i, current_spec in enumerate(chapter_specs):
            chapters_done = chapter_specs[:i]
            chapters_todo = chapter_specs[i + 1 :]

            print(
                f"Processing Chapter {current_spec.chapter_number}: {current_spec.chapter.name}"
            )

            book_progress = show_progress(
                chapters_done,
                current_spec,
                chapters_todo,
                name_function=lambda c: c.chapter.name,
            )

            self._process_single_chapter(i, chapter_specs, book_progress)
            print(f"Chapter {current_spec.chapter_number} completed.")

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
                )
                chapter_specs.append(specs)
        return chapter_specs

    def _process_back_cover(self):
        """Saves the back cover description."""
        if self.writer.back_cover_exists():
            print("Back cover already exists, skipping.")
            return

        print("Saving back cover...")
        self.writer.save_back_cover(self.book_plan.back_cover_description)

    def _process_part_intros(self):
        """Saves the part introductions."""
        for i, part in enumerate(self.book_plan.parts):
            part_number = i + 1
            if self.writer.part_intro_exists(part_number):
                print(f"Part {part_number} intro already exists, skipping.")
                continue

            print(f"Saving Part {part_number} intro...")
            part_label = get_part_label(self.book_plan.book_language)
            content = (
                f"# {part_label} {part_number}: {part.name}\n\n{part.introduction}"
            )
            self.writer.save_part_intro(part_number, content)

    def execute(self):
        """Executes the entire book generation plan."""
        self._process_back_cover()
        self._process_part_intros()
        chapter_specs = self._build_chapter_specs()
        self._process_all_chapters(chapter_specs)
        print(f"Execution completed. Total Cost: ${self.tracker.total_cost:.6f}")


def execute_plan(folder: str):
    root_folder = Path("books") / folder
    plan_yaml = root_folder / "plan.yaml"

    ready_flag = root_folder / "_ready"
    if ready_flag.exists():
        print(f"Book '{folder}' is marked as ready (found {ready_flag}). Skipping.")
        return

    if not plan_yaml.exists():
        print(f"Plan file not found at {plan_yaml}. Please run chapter_based.plan first.")
        return

    print(f"Loading plan from {plan_yaml}...")
    with plan_yaml.open("rt", encoding="utf-8") as f_in:
        data = yaml.safe_load(f_in)
        book_plan = BookPlan.model_validate(data)

    writer = FileSystemWriter(root_folder)
    executor = BookExecutor(book_plan, writer)
    executor.execute()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        execute_plan(sys.argv[1])
    else:
        available_plans = list_available_plan_folders()
        selected_plan = prompt_for_plan_selection(available_plans)
        if selected_plan:
            execute_plan(selected_plan)
