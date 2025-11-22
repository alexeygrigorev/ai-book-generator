from pydantic import BaseModel
from dataclasses import dataclass

class BookSectionPlan(BaseModel):
    name: str
    bullet_points: list[str]

class BookChapterPlan(BaseModel):
    name: str
    # chapter_intro: str
    sections: list[BookSectionPlan]

class BookPartPlan(BaseModel):
    name: str
    introduction: str
    chapters: list[BookChapterPlan]

class BookPlan(BaseModel):
    name: str
    target_reader: str
    back_cover_description: str
    parts: list[BookPartPlan]

@dataclass
class ChapterSpecs:
    part: BookPartPlan
    part_number: int

    chapter: BookChapterPlan
    chapter_number: int

    sections: list[BookSectionPlan]
