"""
Generate Amazon KDP interior PDF using Docker.

Creates a print-ready PDF with:
- 6x9 inch page size
- Mirror margins (gutter)
- Proper typography (XeLaTeX + DejaVu fonts)
- Table of Contents
- Aggregated markdown content

Usage:
    uv run python create_kdp_interior.py book_folder_name
"""

import sys
import os
import yaml
import subprocess
from pathlib import Path
import re

DOCKER_IMAGE_NAME = "kdp-generator"


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
    """
    lines = content.split("\n")
    new_lines = []
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
                full_content.append(content)
                full_content.append("\n\n")

        # Process Chapters and Sections
        files = get_sorted_files(part_dir)
        for filename in files:
            file_path = part_dir / filename
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if filename.endswith("_00_intro.md"):
                # Chapter Intro: Shift H1 -> H2
                content = shift_headers(content, 1)
            else:
                # Section: Shift H2 -> H3
                content = shift_headers(content, 1)

            full_content.append(content)
            full_content.append("\n\n")

    return "".join(full_content)


def build_docker_image():
    """Builds the Docker image if it doesn't exist."""
    print("Checking Docker image...")
    try:
        subprocess.run(
            ["docker", "inspect", DOCKER_IMAGE_NAME],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Docker image '{DOCKER_IMAGE_NAME}' already exists.")
    except subprocess.CalledProcessError:
        print(f"Building Docker image '{DOCKER_IMAGE_NAME}'...")
        try:
            subprocess.run(
                ["docker", "build", "-t", DOCKER_IMAGE_NAME, "."],
                check=True,
                cwd=Path(__file__).parent,
            )
            print("Docker image built successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error building Docker image: {e}")
            sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python create_kdp_interior.py <book_folder_name>")
        sys.exit(1)

    book_name = sys.argv[1]
    base_dir = Path(__file__).parent
    book_dir = base_dir / "books" / book_name

    if not book_dir.exists():
        print(f"Error: Book directory {book_dir} does not exist.")
        sys.exit(1)

    # Ensure Docker image is ready
    build_docker_image()

    print(f"Processing book: {book_name}")

    # Load Metadata
    plan = load_plan(book_dir)
    title = plan.get("name", "Untitled Book")
    language = plan.get("book_language", "en")
    author = plan.get("author", "A.I. Grigorev")

    # Collect Content
    print("Collecting markdown content...")
    markdown_content = collect_markdown_content(book_dir)

    # Save temporary combined markdown
    temp_md_filename = f"{book_name}_interior.md"
    temp_md_path = book_dir / temp_md_filename
    with open(temp_md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    # Output PDF filename
    output_pdf_filename = "kdp_interior.pdf"
    output_pdf_path = book_dir / output_pdf_filename

    # Docker Command
    # We mount the 'books' directory to /data in the container
    # So inside container: /data/book_name/file.md

    books_root_abs = (base_dir / "books").resolve()
    container_book_dir = f"/data/{book_name}"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{books_root_abs}:/data",
        DOCKER_IMAGE_NAME,
        f"{container_book_dir}/{temp_md_filename}",
        "-o",
        f"{container_book_dir}/{output_pdf_filename}",
        "--pdf-engine=xelatex",
        "--toc",
        f"--metadata=title:{title}",
        f"--metadata=author:{author}",
        f"--metadata=lang:{language}",
        "--top-level-division=part",
        # KDP 6x9" Geometry
        "-V",
        "geometry:paperwidth=6in",
        "-V",
        "geometry:paperheight=9in",
        "-V",
        "geometry:margin=0.75in",
        "-V",
        "geometry:inner=0.75in",  # Gutter
        "-V",
        "geometry:outer=0.5in",
        "-V",
        "geometry:top=0.75in",
        "-V",
        "geometry:bottom=0.75in",
        # Fonts
        "-V",
        "mainfont=DejaVu Serif",
        "-V",
        "sansfont=DejaVu Sans",
        "-V",
        "monofont=DejaVu Sans Mono",
        "-V",
        "documentclass=book",
    ]

    print(f"Running Docker to generate PDF...")
    try:
        subprocess.run(cmd, check=True)
        print(f"[OK] KDP interior PDF generated: {output_pdf_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error running Docker command: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if temp_md_path.exists():
            os.remove(temp_md_path)


if __name__ == "__main__":
    main()
