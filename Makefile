# AI Book Generator - Makefile
# Convenient targets for running scripts and common operations

.PHONY: help ui generate-book tts ebook kdp-interior kdp-cover convert-audio setup-aws clean

# Default target - show help
help:
	@echo "AI Book Generator - Available Commands"
	@echo "======================================="
	@echo ""
	@echo "Main Commands:"
	@echo "  make ui                  - Launch Streamlit UI for book planning"
	@echo "  make generate-book       - Generate book content using AI"
	@echo ""
	@echo "Audio & Publishing:"
	@echo "  make tts BOOK=<name>     - Generate TTS audio for a book"
	@echo "  make convert-audio       - Convert WAV files to MP3 in S3"
	@echo "  make ebook BOOK=<name>   - Create EPUB ebook"
	@echo ""
	@echo "KDP Publishing:"
	@echo "  make kdp-interior BOOK=<name> - Generate KDP interior PDF"
	@echo "  make kdp-cover BOOK=<name>    - Generate KDP cover PDF"
	@echo ""
	@echo "Setup & Utilities:"
	@echo "  make setup-aws           - Create S3 reader IAM user"
	@echo "  make clean               - Remove generated files"
	@echo "  make test                - Run tests"
	@echo ""
	@echo "Examples:"
	@echo "  make tts BOOK=sirens"
	@echo "  make ebook BOOK=metals"
	@echo "  make kdp-interior BOOK=sirens"

# Launch Streamlit UI
ui:
	@echo "Launching Streamlit UI..."
	uv run python main.py

# Generate book using the book_generator module
generate-book:
	@echo "Generating book content..."
	uv run python -m book_generator.execute

# Generate TTS audio
tts:
ifndef BOOK
	@echo "Error: BOOK parameter required"
	@echo "Usage: make tts BOOK=<book_name>"
	@exit 1
endif
	@echo "Generating TTS for book: $(BOOK)"
	uv run python scripts/run_tts.py $(BOOK)

# Convert WAV to MP3
convert-audio:
	@echo "Converting WAV files to MP3..."
	uv run python scripts/convert_wav_to_mp3.py

# Convert to EPUB
ebook:
ifndef BOOK
	@echo "Converting available books to EPUB..."
	uv run python scripts/convert_to_ebook.py
else
	@echo "Converting book to EPUB: $(BOOK)"
	uv run python scripts/convert_to_ebook.py $(BOOK)
endif

# Generate KDP interior PDF
kdp-interior:
ifndef BOOK
	@echo "Error: BOOK parameter required"
	@echo "Usage: make kdp-interior BOOK=<book_name>"
	@exit 1
endif
	@echo "Generating KDP interior for: $(BOOK)"
	uv run python scripts/create_kdp_interior.py $(BOOK)

# Generate KDP cover PDF
kdp-cover:
ifndef BOOK
	@echo "Error: BOOK parameter required"
	@echo "Usage: make kdp-cover BOOK=<book_name>"
	@exit 1
endif
	@echo "Generating KDP cover for: $(BOOK)"
	uv run python scripts/create_kdp_cover.py $(BOOK)


# Run tests
test:
	@echo "Running tests..."
	uv run pytest
