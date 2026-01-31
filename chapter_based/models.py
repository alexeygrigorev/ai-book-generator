from pydantic import BaseModel
from dataclasses import dataclass
from typing import Literal


class ChapterPlan(BaseModel):
    name: str
    bullet_points: list[str]  # 7-8 bullet points outlining the chapter content


class BookPartPlan(BaseModel):
    name: str
    introduction: str
    chapters: list[ChapterPlan]


class BookPlan(BaseModel):
    book_language: Literal["ru", "en", "de"]
    name: str
    slug: str  # Filesystem-safe short name
    target_reader: str
    back_cover_description: str
    parts: list[BookPartPlan]


@dataclass
class ChapterSpecs:
    part: BookPartPlan
    part_number: int

    chapter: ChapterPlan
    chapter_number: int
