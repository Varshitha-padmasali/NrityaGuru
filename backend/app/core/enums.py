"""Enums shared by models, schemas and services (no framework imports)."""
import enum


class VerificationStatus(str, enum.Enum):
    """How far a record has been checked.

    unverified   - no supporting source yet; never used as authoritative.
    source_cited - taken from a named source, NOT yet cross-checked by an expert/primary text.
    verified     - cross-checked (primary text and/or a qualified teacher). Only this is
                   returned by default.
    """

    UNVERIFIED = "unverified"
    SOURCE_CITED = "source_cited"
    VERIFIED = "verified"


class MatchType(str, enum.Enum):
    """Why a record was retrieved for a concept (strongest first)."""

    CONCEPT_MAPPING = "concept_mapping"  # explicit curated mapping
    EXACT_NAME = "exact_name"  # concept equals the record's name
    ALTERNATE_NAME = "alternate_name"  # concept equals an alternate name
    USAGE_LISTED = "usage_listed"  # concept equals an item in the record's listed usages
    USAGE_KEYWORD = "usage_keyword"  # concept is one word inside a listed usage (weak)


class TutorFallbackReason(str, enum.Enum):
    """Why the tutor returned retrieved knowledge instead of an AI explanation."""

    NO_REFERENCES = "no_references"  # nothing supported to explain (Gemini not called)
    NOT_CONFIGURED = "not_configured"  # no API key / SDK missing
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"  # 5xx / network problems
    AUTH_OR_MODEL_ERROR = "auth_or_model_error"  # 401 / 403 / 404 (bad key or model id)
    REQUEST_ERROR = "request_error"  # other 4xx
    EMPTY_RESPONSE = "empty_response"
    MALFORMED_OUTPUT = "malformed_output"  # not valid JSON / wrong schema
    INVALID_CITATION = "invalid_citation"  # cited an id that was not retrieved
    UNGROUNDED_OUTPUT = "ungrounded_output"  # claims not backed by retrieved records
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # feedback only: evidence too weak (Gemini not called)


class EvaluationErrorCode(str, enum.Enum):
    """Why evaluation evidence was rejected. Part 8 maps these to HTTP status codes."""

    INVALID_SESSION_ID = "invalid_session_id"  # bad format
    SESSION_NOT_FOUND = "session_not_found"
    SESSION_MISMATCH = "session_mismatch"  # store returned a different session
    MALFORMED_RESULT = "malformed_result"  # fails the contract schema
    UNSUPPORTED_VERSION = "unsupported_version"
    UNKNOWN_REFERENCE = "unknown_reference"  # mudra/movement missing or not available
    MOCK_DATA_IN_REAL_STORE = "mock_data_in_real_store"
    STORE_UNAVAILABLE = "store_unavailable"  # evaluation integration not configured/reachable
