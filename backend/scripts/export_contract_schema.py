"""Write the contract as JSON Schema for the evaluation teammate.  From backend/:
    python -m scripts.export_contract_schema
Creates docs/evaluation_result.schema.json (needs the real pydantic, i.e. your venv)."""
import json
from pathlib import Path

from app.schemas.evaluation import EvaluationResult


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "docs" / "evaluation_result.schema.json"
    out.write_text(json.dumps(EvaluationResult.model_json_schema(), indent=2), encoding="utf-8")
    print("Wrote", out)


if __name__ == "__main__":
    main()
