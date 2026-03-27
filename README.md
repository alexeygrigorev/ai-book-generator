# AI Book Generator

An AI-powered system for creating complete books with text content, audio narration, and print-ready formats for Amazon KDP publishing.

## Features

- 📝 AI-powered book content generation (using Google Gemini)
- 🎙️ Text-to-speech audio generation with S3 storage
- 📚 EPUB ebook creation
- 📖 Amazon KDP print-ready PDF generation (interior & cover)
- 🌐 Interactive Streamlit UI for book planning
- 🔄 Parallel TTS processing with graceful interruption
- ☁️ AWS S3 integration for audio storage

## Quick Start

### Launch the UI
```bash
# Using make
make ui

# Or directly
python main.py

# Or with uv
uv run python main.py
```

### Generate a Book
```bash
# Interactive mode (with UI)
make ui

# CLI mode
make generate-book
```

## Two Generation Modes

| Aspect | Section-Based (`book_generator/`) | Chapter-Based (`chapter_based/`) |
|--------|-----------------------------------|----------------------------------|
| Generation unit | Per section (800-1200 words) | Per chapter (3000-5000 words) |
| LLM calls per chapter | 1 intro + 4-6 sections = 5-7 calls | 1 call per chapter |
| Best for | Longer, detailed books | Shorter, cohesive books |
| Plan structure | Chapters → Sections → Bullet points | Chapters → Bullet points |

```bash
# Section-based (longer books)
uv run python -m book_generator.plan -p books/mybook/input.txt
uv run python -m book_generator.execute mybook

# Chapter-based (shorter books)
uv run python -m chapter_based.plan -p books/mybook/input.txt
uv run python -m chapter_based.execute mybook
```

## Project Structure

```
ai-book-generator/
├── book_generator/          # Section-based generation (longer books)
│   ├── execute.py          # Main execution module
│   ├── plan.py             # Book planning and structuring
│   ├── content.py          # Content generation
│   ├── tts.py              # Text-to-speech generation
│   └── ...
├── chapter_based/           # Chapter-based generation (shorter books)
│   ├── execute.py          # Generates one full chapter at a time
│   ├── plan.py             # Creates plan with bullet points per chapter
│   ├── models.py           # Data models
│   └── README.md           # Detailed comparison of both modes
├── scripts/                # Utility scripts
│   ├── run_tts.py          # TTS generation runner
│   ├── convert_wav_to_mp3.py   # Audio format conversion
│   ├── convert_to_ebook.py     # EPUB generation
│   ├── create_kdp_interior.py  # KDP interior PDF
│   ├── create_kdp_cover.py     # KDP cover PDF
│   └── create_s3_reader_user.py # AWS IAM setup
├── ui/                     # User interfaces
│   └── streamlit_app.py    # Streamlit web interface
├── books/                  # Generated books storage
├── audio/                  # Local audio files cache
├── tests/                  # Test files
├── main.py                 # Main entry point
├── Makefile               # Convenient command shortcuts
└── README.md              # This file
```

## Scripts Documentation

### Core Generation

#### `book_generator/execute.py`
Purpose: Main book content generation module

Generates complete book content including:
- Structured book plans with parts and chapters
- Section content with proper hierarchy
- Part introductions
- Metadata and back cover descriptions

Usage:
```bash
uv run python -m book_generator.execute
```

### Audio Processing

#### `scripts/run_tts.py`
Purpose: Generate text-to-speech audio for book content

Features:
- Parallel processing with configurable thread count
- S3 upload for generated audio
- Progress tracking
- Skips already-generated files

Usage:
```bash
# Via make
make tts BOOK=sirens

# Direct
python scripts/run_tts.py
```

Configuration: Edit the script to change book folder or thread count.

---

#### `scripts/convert_wav_to_mp3.py`
Purpose: Convert WAV audio files in S3 bucket to MP3 format

Features:
- Downloads WAV from S3
- Converts using ffmpeg
- Uploads MP3 back to S3
- Skips files already converted
- Keeps local MP3 cache

Usage:
```bash
# Via make
make convert-audio

# Direct with options
python scripts/convert_wav_to_mp3.py --book sirens
python scripts/convert_wav_to_mp3.py --source-bucket my-bucket
```

Arguments:
- `--book`: Optional book name filter
- `--source-bucket`: S3 bucket with WAV files (default: ai-generated-audio-books-eu-west-1-wav)
- `--output-bucket`: Destination bucket (defaults to source bucket)

### Publishing

#### `scripts/convert_to_ebook.py`
Purpose: Convert markdown book to EPUB format

Features:
- Aggregates markdown from book structure
- Adds metadata (title, author, language)
- Includes table of contents
- Embeds cover image (JPG/PNG)
- Proper header hierarchy

Usage:
```bash
# Via make (interactive selection)
make ebook

# Via make (specific book)
make ebook BOOK=sirens

# Direct
python scripts/convert_to_ebook.py mir-na-trosakh
```

Requirements: Pandoc must be installed

---

#### `scripts/create_kdp_interior.py`
Purpose: Generate Amazon KDP print interior PDF

Features:
- 6×9 inch page size (KDP standard)
- Mirror margins with gutter
- XeLaTeX for proper typography
- Cyrillic font support (DejaVu)
- Table of contents
- Docker-based (reproducible builds)

Usage:
```bash
# Via make
make kdp-interior BOOK=sirens

# Direct
python scripts/create_kdp_interior.py sirens
```

Requirements: Docker must be installed and running

---

#### `scripts/create_kdp_cover.py`
Purpose: Generate Amazon KDP cover PDF with back cover, spine, and front cover

Features:
- Automatic spine width calculation
- Back cover with description text
- Front cover with image or generated design
- Crop marks and bleed area
- Cyrillic text support
- KDP-compliant dimensions

Usage:
```bash
# Via make
make kdp-cover BOOK=sirens

# Direct
uv run python scripts/create_kdp_cover.py sirens

uv run python scripts/create_kdp_cover.py metals-pocketbook  --pages 80
```

Arguments:
- Book name (required)
- `--pages`: Page count for spine calculation (optional, auto-detects from PDF)

### Setup & Configuration

#### `scripts/create_s3_reader_user.py`
Purpose: Create AWS IAM user with S3 read/write access for TTS audio

Creates:
- IAM user: `tts-audio-reader`
- S3 read/write policy for the audio bucket
- Access keys for authentication

Usage:
```bash
# Via make
make setup-aws

# Direct
python scripts/create_s3_reader_user.py
```

Output: Displays AWS credentials to add to `.envrc` or environment

### User Interface

#### `ui/streamlit_app.py`
Purpose: Interactive web interface for book planning

Features:
- Book topic configuration
- Size selection (small/medium/large)
- AI-powered plan generation with streaming
- Interactive refinement chat
- Cost tracking
- Structured plan export to YAML

Usage:
```bash
# Via make
make ui

# Via main.py
python main.py

# Direct
streamlit run ui/streamlit_app.py
```

## Makefile Commands

The project includes a Makefile for convenient command execution:

```bash
make help              # Show all available commands
make ui                # Launch Streamlit UI
make generate-book     # Generate book content
make tts BOOK=name     # Generate TTS audio
make convert-audio     # Convert WAV to MP3
make ebook BOOK=name   # Create EPUB
make kdp-interior BOOK=name   # Generate KDP interior PDF
make kdp-cover BOOK=name      # Generate KDP cover PDF
make setup-aws         # Create AWS IAM user
make test              # Run tests
make clean             # Remove generated files
```

## Development

### Running Tests
```bash
make test
# or
uv run pytest
```

### Project Dependencies
- Python 3.10+
- Google Gemini API (for content generation)
- AWS S3 (for audio storage)
- Pandoc (for ebook conversion)
- Docker (for KDP PDF generation)
- ffmpeg (for audio conversion)

### Environment Setup
1. Install dependencies: `uv sync`
2. Configure AWS credentials (see `make setup-aws`)
3. Set up Google Gemini API key
4. Install system dependencies (pandoc, docker, ffmpeg)

## Book Output Structure

Each generated book has the following structure:

```
books/
└── book-name/
    ├── plan.yaml              # Book metadata and structure
    ├── back_cover.md          # Back cover description
    ├── cover.jpg              # Cover image
    ├── book-name.epub         # Generated ebook
    ├── kdp_interior.pdf       # Print interior
    ├── kdp_cover.pdf          # Print cover
    └── part_01/               # Book parts
        ├── _part_01_intro.md  # Part introduction
        ├── 01_00_intro.md     # Chapter intro
        ├── 01_01_section.md   # Sections
        └── ...
```

## License

[Your License Here]

## Author

A.I. Grigorev