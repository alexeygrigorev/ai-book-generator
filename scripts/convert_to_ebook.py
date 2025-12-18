import os
import sys
import yaml
import subprocess
import re
from pathlib import Path

import questionary


def load_plan(book_dir):
    plan_path = book_dir / "plan.yaml"
    if not plan_path.exists():
        print(f"Error: plan.yaml not found in {book_dir}")
        sys.exit(1)

    with open(plan_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def shift_headers(content, shift_by):
    """
    Shifts markdown headers by a specified amount.
    e.g. if shift_by is 1, # becomes ##, ## becomes ###
    """
    lines = content.split("\n")
    new_lines = []
    # Regex to match markdown headers (at start of line)
    # We only shift headers that are 1-6 hashes long
    header_regex = re.compile(r"^(#{1,6})\s+(.*)")

    for line in lines:
        match = header_regex.match(line)
        if match:
            hashes, text = match.groups()
            new_hashes = "#" * (len(hashes) + shift_by)
            new_lines.append(f"{new_hashes} {text}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)


def get_sorted_parts(book_dir):
    parts = []
    for item in os.listdir(book_dir):
        if os.path.isdir(book_dir / item) and item.startswith("part_"):
            parts.append(item)
    return sorted(parts)


def get_sorted_files(part_dir):
    files = []
    for item in os.listdir(part_dir):
        if item.endswith(".md") and not item.startswith("_"):
            files.append(item)
    return sorted(files)


def collect_markdown_content(book_dir):
    full_content = []

    # 1. Add Title Page info (optional, pandoc handles metadata, but good to have in text)
    # We'll skip explicit title page in markdown and let pandoc metadata handle it.

    parts = get_sorted_parts(book_dir)

    for part_name in parts:
        part_dir = book_dir / part_name
        # Extract part number from part_name (e.g., "part_01" -> "01")
        part_number = part_name.split("_")[1]

        # Process Part Intro
        part_intro_path = part_dir / f"_part_{part_number}_intro.md"
        if part_intro_path.exists():
            with open(part_intro_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Part intro is usually H1 (# Часть X...), keep it as H1
                full_content.append(content)
                full_content.append("\n\n")

        # Process Chapters and Sections
        files = get_sorted_files(part_dir)
        for filename in files:
            file_path = part_dir / filename
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if filename.endswith("_00_intro.md"):
                # Chapter Intro. Currently H1 (# 1. Chapter...).
                # We want it to be H2 to sit under Part (H1).
                # Shift by 1.
                content = shift_headers(content, 1)
            else:
                # Section. Currently H2 (## Section...).
                # We want it to be H3.
                # Shift by 1.
                content = shift_headers(content, 1)

            full_content.append(content)
            full_content.append("\n\n")

    return "".join(full_content)


def list_available_book_folders(books_root: Path) -> list[Path]:
    """Returns book folders that have a plan."""
    if not books_root.exists():
        return []

    available = []
    for folder in sorted(books_root.iterdir()):
        if not folder.is_dir():
            continue

        if (folder / "plan.yaml").exists():
            available.append(folder)
    return available


def prompt_for_book_selection(plan_folders: list[Path]) -> str | None:
    """Prompts the user to select a book folder."""
    if not plan_folders:
        print("No available books found in books/.")
        return None

    return questionary.select(
        "Select a book to convert to EPUB",
        choices=[
            questionary.Choice(title=folder.name, value=folder.name)
            for folder in plan_folders
        ],
        default=plan_folders[0].name,
    ).ask()


def main():
    base_dir = Path(__file__).parent.parent
    books_root = base_dir / "books"

    if len(sys.argv) >= 2:
        book_name = sys.argv[1]
    else:
        plan_folders = list_available_book_folders(books_root)
        selected = prompt_for_book_selection(plan_folders)
        if not selected:
            sys.exit(0)
        book_name = selected

    book_dir = books_root / book_name

    if not book_dir.exists():
        print(f"Error: Book directory {book_dir} does not exist.")
        sys.exit(1)
    print(f"Processing book: {book_name}")

    # Load Metadata
    plan = load_plan(book_dir)
    title = plan.get("name", "Untitled Book")
    language = plan.get("book_language", "en")
    # Author is not in plan.yaml usually, defaulting to "AI Author" or checking if it's there
    author = plan.get("author", "A.I. Grigorev")

    # Collect Content
    print("Collecting markdown content...")
    markdown_content = collect_markdown_content(book_dir)

    # Save temporary combined markdown
    temp_md_path = book_dir / f"{book_name}_combined.md"
    with open(temp_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # Output EPUB path
    output_epub = book_dir / f"{book_name}.epub"

    # Build Pandoc Command
    # --toc: Table of Contents
    # --metadata: Set metadata fields
    # --top-level-division=part: Helps pandoc understand the structure (though we manually shifted headers)
    cmd = [
        "pandoc",
        str(temp_md_path),
        "-o",
        str(output_epub),
        "--toc",
        f"--metadata=title:{title}",
        f"--metadata=author:{author}",
        f"--metadata=lang:{language}",
        "--top-level-division=part",
    ]

    # Add cover if exists (supports jpg, jpeg, and png extensions)
    cover_extensions = [".jpg", ".jpeg", ".png"]
    cover_path = None
    for ext in cover_extensions:
        potential_cover = book_dir / f"cover{ext}"
        if potential_cover.exists():
            cover_path = potential_cover
            break

    if cover_path:
        cmd.append(f"--epub-cover-image={cover_path}")
        print(f"Using cover image: {cover_path.name}")

    # Print command safely (handling non-ASCII characters in Windows console)
    print(f"Running pandoc to create {output_epub.name}...")

    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully created: {output_epub}")
    except subprocess.CalledProcessError as e:
        print(f"Error running pandoc: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: pandoc not found. Please install pandoc.")
        sys.exit(1)

    # Cleanup temp file
    if temp_md_path.exists():
        os.remove(temp_md_path)


if __name__ == "__main__":
    main()
