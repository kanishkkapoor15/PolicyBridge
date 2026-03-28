from pydantic import BaseModel


class RetrievalResult(BaseModel):
    chunk_text: str
    source_framework: str
    section_title: str
    relevance_score: float
    source_file: str
