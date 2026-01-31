# Chapter-Based Book Generator

This variant generates **one full chapter at a time** instead of generating section-by-section.

## Quick Comparison

### Section-Based (`book_generator/`) — Original
```bash
# 1. Generate plan (chapters contain sections with bullet points)
uv run python -m book_generator.plan -p books/mybook/input.txt

# 2. Generate content (one section at a time, 800-1200 words each)
uv run python -m book_generator.execute mybook
```

### Chapter-Based (`chapter_based/`) — This Variant
```bash
# 1. Generate plan (chapters have bullet points directly)
uv run python -m chapter_based.plan -p books/mybook/input.txt

# 2. Generate content (one full chapter at a time, 3000-5000 words each)
uv run python -m chapter_based.execute mybook
```

## When to Use Which

| Aspect | Section-Based | Chapter-Based |
|--------|---------------|---------------|
| **Generation unit** | Per section (800-1200 words) | Per chapter (3000-5000 words) |
| **LLM calls per chapter** | 1 intro + 4-6 sections = 5-7 calls | 1 full chapter = 1 call |
| **Cohesion** | Sections stitched together | Chapter written as one piece |
| **Best for** | Very large books, want granular control | Smaller books, want cohesive chapters |
| **Cost** | More LLM calls = potentially higher cost | Fewer LLM calls = potentially lower cost |
| **Interruption resume** | Can resume mid-chapter | Resumes at chapter boundaries |

## Usage

### Option A: Convert an Existing Outline

If you already have a detailed outline (like the `kak_mashiny_dvigayutsya.md` example), convert it directly:

```bash
uv run python -m chapter_based.plan \
  --prompt-file books/how-machines-move-ru/kak_mashiny_dvigayutsya.md \
  --output books/how-machines-move-ru/plan.yaml
```

Your outline format should be:
```markdown
# Book Title
*Subtitle*

## Chapter 1: Title
- bullet point 1
- bullet point 2
...

## Chapter 2: Title
- bullet point 1
...
```

### Option B: Create a Plan from a Description

Create an input file with your book idea:

```bash
cat > books/mybook-chapter/input.txt << 'EOF'
I want to write a book about practical Python programming for beginners.
The book should cover:
- Setting up Python environment
- Basic syntax and data types
- Functions and modules
- Working with files
- Error handling
- Small projects to practice

Language: English
Size: Medium (about 8-10 chapters)
EOF
```

Then generate the plan:

```bash
uv run python -m chapter_based.plan \
  --prompt-file books/mybook-chapter/input.txt \
  --output books/mybook-chapter/plan.yaml
```

The planner will expand your idea into chapters with 7-8 bullet points each.

### Generate the Book Content

```bash
uv run python -m chapter_based.execute mybook-chapter
```

Or run without arguments to select from available chapter-based plans:

```bash
uv run python -m chapter_based.execute
```

## Plan Structure

The chapter-based plan YAML structure:

```yaml
book_language: en
name: Your Book Title
slug: your-book-title
target_reader: Description of target audience
back_cover_description: Back cover text
parts:
  - name: Part 1 Name
    introduction: Introduction to this part
    chapters:
      - name: Chapter Name
        bullet_points:
          - First key topic
          - Second key topic
          - ... (7-8 bullet points total)
```

## Output Structure

```
books/your-book-title/
├── plan.yaml
├── back_cover.md
└── part_01/
    ├── _part_01_intro.md
    ├── 01_chapter.md
    ├── 02_chapter.md
    └── ...
```

## Key Differences from Section-Based

| Feature | Section-Based | Chapter-Based |
|---------|---------------|---------------|
| Plan location | `book_generator/plan.py` | `chapter_based/plan.py` |
| Execute location | `book_generator/execute.py` | `chapter_based/execute.py` |
| Plan model | `BookSectionPlan` inside chapters | `ChapterPlan` with bullet_points |
| Generation unit | Per section (800-1200 words) | Per chapter (3000-5000 words) |
| Output files | `01_01_section.md`, `01_02_section.md` | `01_chapter.md`, `02_chapter.md` |
| LLM calls per chapter | 1 intro + N sections | 1 full chapter |
