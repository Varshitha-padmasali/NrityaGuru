"""Parsing and grounding checks for Gemini output.

Pydantic checks the SHAPE. check_grounding checks the CLAIMS against what was retrieved:
no fabricated ids, no unknown concepts, no support claimed where nothing was retrieved.
It cannot prove the wording is faithful; that needs human review (Part 6 evaluation).
"""
import json

from pydantic import ValidationError

from app.schemas.knowledge import RetrievalResponse
from app.schemas.tutor import TutorExplanation
from app.services.tutor_prompt import collect_citable_ids, concept_citable_ids


class MalformedOutputError(ValueError):
    pass


class InvalidCitationError(ValueError):
    pass


class UngroundedOutputError(ValueError):
    pass


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()[1:]  # drop the opening fence (``` or ```json)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise MalformedOutputError("The model output is not valid JSON.") from None
    if not isinstance(data, dict):
        raise MalformedOutputError("The model output is not a JSON object.")
    return data


def check_grounding(explanation: TutorExplanation, retrieval: RetrievalResponse) -> None:
    allowed = collect_citable_ids(retrieval)

    cited = set(explanation.source_ids)
    for item in explanation.concepts:
        cited |= set(item.source_ids)
    unknown = cited - allowed
    if unknown:
        raise InvalidCitationError(f"{len(unknown)} cited id(s) were not in the retrieved knowledge.")

    by_name = {}
    for cr in retrieval.concepts:
        names = {cr.concept.text, cr.concept.normalized, *cr.concept.lookup_keys}
        for name in names:
            by_name.setdefault(name.casefold(), cr)

    for item in explanation.concepts:
        cr = by_name.get(item.concept.strip().casefold())
        if cr is None:
            raise UngroundedOutputError("The output discusses a concept that was not in the input.")
        if not cr.references:
            if item.supported or item.source_ids:
                raise UngroundedOutputError("Support was claimed for a concept with no retrieved reference.")
            continue
        if item.supported and not item.source_ids:
            raise UngroundedOutputError("A supported concept has no citation.")
        if set(item.source_ids) - concept_citable_ids(cr):
            raise InvalidCitationError("A concept cites ids that belong to a different concept.")


def validate_explanation(raw: dict, retrieval: RetrievalResponse) -> TutorExplanation:
    try:
        explanation = TutorExplanation.model_validate(raw)
    except ValidationError:
        raise MalformedOutputError("The model output does not match the expected structure.") from None
    check_grounding(explanation, retrieval)
    return explanation
