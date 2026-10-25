"""The complete RAG flow:  text -> concepts -> retrieval -> tutor (Gemini) -> validated answer.

Retrieval and generation are injected so each can be tested alone. The retrieved knowledge is
ALWAYS part of the response, so the learner still gets the information if Gemini fails.
"""
from collections.abc import Callable

from app.schemas.knowledge import RetrievalResponse
from app.schemas.rag import TutorExplainResponse
from app.services.tutor_service import TutorService

RetrieveFn = Callable[..., RetrievalResponse]  # (text, *, include_unverified, include_keyword_matches)


class RagPipeline:
    def __init__(self, retrieve: RetrieveFn, tutor: TutorService) -> None:
        self._retrieve = retrieve
        self._tutor = tutor

    def run(
        self,
        text: str,
        *,
        include_unverified: bool = False,
        include_keyword_matches: bool = False,
    ) -> TutorExplainResponse:
        # Raises InputValidationError for unusable input (the API turns it into a 422).
        retrieval = self._retrieve(
            text,
            include_unverified=include_unverified,
            include_keyword_matches=include_keyword_matches,
        )
        tutor_result = self._tutor.explain(retrieval)
        return TutorExplainResponse(
            original_text=retrieval.original_text,
            tutor=tutor_result,
            retrieval=retrieval,
        )
