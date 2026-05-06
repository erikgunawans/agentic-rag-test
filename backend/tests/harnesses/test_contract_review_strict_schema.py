"""Regression test for UAT-NEW-01 (Azure strict-mode schema validation).

Every Pydantic model passed to OpenRouter as response_format with strict: True
must emit additionalProperties: false in its JSON schema. Pydantic v2's default
output omits this field, which Azure's gpt-4o deployment rejects with HTTP 400.

This test walks the contract-review harness registry and asserts compliance
for every PhaseDefinition with a non-None output_schema, plus HumanInputQuestion
which is used directly in _dispatch_llm_human_input.
"""

from app.harnesses.contract_review import CONTRACT_REVIEW
from app.harnesses.types import PhaseType
from app.services.harness_engine import HumanInputQuestion


def _walk_schema_object_types(schema: dict):
    """Yield every dict in the schema that represents a JSON Schema "object" type.

    Azure strict mode requires every object schema (top-level AND nested in $defs)
    to have additionalProperties: false. We yield each such dict so the caller
    can assert on it directly.
    """
    # Top-level: contract objects always have a "properties" or "type": "object"
    if schema.get("type") == "object" or "properties" in schema:
        yield schema

    # $defs: nested model definitions
    for def_name, def_schema in (schema.get("$defs") or {}).items():
        if def_schema.get("type") == "object" or "properties" in def_schema:
            yield def_schema


def test_human_input_question_is_strict_compliant():
    """HumanInputQuestion is used by _dispatch_llm_human_input with strict: True."""
    schema = HumanInputQuestion.model_json_schema()
    for obj in _walk_schema_object_types(schema):
        assert obj.get("additionalProperties") is False, (
            f"HumanInputQuestion schema (or one of its $defs) is missing "
            f"additionalProperties: false. Azure strict mode will reject this. "
            f"Add `model_config = ConfigDict(extra=\"forbid\")` to the model."
        )


def test_every_output_schema_is_strict_compliant():
    """Every PhaseDefinition.output_schema in the contract-review harness must
    emit additionalProperties: false at top level and for every $defs object.

    Future-proofs against a new phase being added with a non-strict schema.
    """
    failures = []
    for phase in CONTRACT_REVIEW.phases:
        if phase.output_schema is None:
            continue
        # Only LLM_SINGLE phases hit the strict response_format path
        if phase.phase_type != PhaseType.LLM_SINGLE:
            continue
        schema = phase.output_schema.model_json_schema()
        for obj in _walk_schema_object_types(schema):
            if obj.get("additionalProperties") is not False:
                failures.append(
                    f"  - phase={phase.name!r} schema={phase.output_schema.__name__!r} "
                    f"object={obj.get('title') or '(top-level)'!r}: "
                    f"additionalProperties={obj.get('additionalProperties')!r}"
                )

    assert not failures, (
        "The following output_schema models lack additionalProperties: false. "
        "Azure strict mode will reject them at runtime. "
        "Add `model_config = ConfigDict(extra=\"forbid\")` to each.\n"
        + "\n".join(failures)
    )


def test_every_output_schema_is_azure_strict_via_helper():
    """Defense-in-depth: walk the harness registry and assert that the
    emission-boundary helper produces fully Azure-strict output for every
    output_schema in CONTRACT_REVIEW.

    Closes plan 22-18 (UAT-NEW-02). Compared to test_every_output_schema_is_strict_compliant,
    this test asserts both strict rules (additionalProperties + required) on the
    helper output rather than on the raw model_json_schema output.
    """
    from app.services.harness_engine import _to_azure_strict_schema, HumanInputQuestion

    failures = []

    def _check(label: str, schema: dict):
        for obj in _walk_schema_object_types(schema):
            if obj.get("additionalProperties") is not False:
                failures.append(
                    f"  - {label}: object {obj.get('title') or '(top-level)'!r} "
                    f"missing additionalProperties: false"
                )
            props = set((obj.get("properties") or {}).keys())
            req = set(obj.get("required") or [])
            if props != req:
                failures.append(
                    f"  - {label}: object {obj.get('title') or '(top-level)'!r} "
                    f"required={sorted(req)} != properties.keys()={sorted(props)}"
                )

    # HumanInputQuestion via the helper
    _check("HumanInputQuestion", _to_azure_strict_schema(HumanInputQuestion))

    # Every output_schema in the contract-review harness via the helper
    for phase in CONTRACT_REVIEW.phases:
        if phase.output_schema is None:
            continue
        if phase.phase_type != PhaseType.LLM_SINGLE:
            continue
        schema = _to_azure_strict_schema(phase.output_schema)
        _check(f"phase={phase.name!r} schema={phase.output_schema.__name__}", schema)

    assert not failures, (
        "Helper-emitted schemas fail Azure strict-mode rules. Each entry "
        "shows the schema-walk path that violated either additionalProperties: "
        "false OR required = properties.keys().\n" + "\n".join(failures)
    )
