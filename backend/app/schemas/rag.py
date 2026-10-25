"""Request/response for the full RAG tutor endpoint (Part 6)."""
from pydantic import BaseModel, Field

from app.schemas.knowledge import RetrievalResponse
from app.schemas.tutor import TutorResult
from app.services.text_processing import MAX_INPUT_CHARS


class TutorExplainRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    include_unverified: bool = False  # needs ALLOW_UNVERIFIED_RECORDS=true on the server
    include_keyword_matches: bool = False


class TutorExplainResponse(BaseModel):
    original_text: str
    tutor: TutorResult  # AI explanation, or knowledge-only fallback (see tutor.mode)
    retrieval: RetrievalResponse  # the retrieved records, ALWAYS returned
    disclaimer: str = (
        "NrityaGuru explains reference information from a curated knowledge base. It is a "
        "learning aid, not a replacement for an experienced Bharatanatyam teacher."
    )
