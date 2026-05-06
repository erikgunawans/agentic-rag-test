"""Unit tests for _to_azure_strict_schema helper (plan 22-18 / UAT-NEW-02).

The helper transforms a Pydantic model's JSON Schema into one that satisfies
OpenAI/Azure strict mode at every "object" node (top-level + every $defs entry):
  - additionalProperties: false
  - required: list of all property keys

Discovered live 2026-05-06 05:42:05Z when Azure-routed gpt-4o rejected
ContractClassification with 'required is required to be supplied and to be
an array including every key in properties. Missing effective_date.'
"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.harness_engine import _to_azure_strict_schema


class _OptionalFieldsModel(BaseModel):
    """Mirrors the real ContractClassification shape: required + optional fields."""

    model_config = ConfigDict(extra="forbid")

    must: str = Field(..., min_length=1)
    optional_str: str | None = Field(None)
    optional_int: int | None = Field(None)


class _NestedModel(BaseModel):
    """Nested object — exercises $defs recursion."""

    model_config = ConfigDict(extra="forbid")
    inner: _OptionalFieldsModel
    inner_optional: _OptionalFieldsModel | None = None


def test_helper_emits_required_for_all_properties():
    """Every key in properties must appear in required (Azure strict rule)."""
    schema = _to_azure_strict_schema(_OptionalFieldsModel)
    props = set((schema.get("properties") or {}).keys())
    req = set(schema.get("required") or [])
    assert req == props, (
        f"required must equal properties.keys() under Azure strict mode. "
        f"missing from required: {props - req}, extra in required: {req - props}"
    )


def test_helper_emits_additional_properties_false():
    """Every object schema must have additionalProperties: false (Azure strict rule).

    This rule was already enforced by plan 22-17's model_config additions, but
    the helper provides defense-in-depth at the emission boundary regardless of
    per-model config.
    """
    schema = _to_azure_strict_schema(_OptionalFieldsModel)
    assert schema.get("additionalProperties") is False


def test_helper_recurses_into_defs():
    """Nested $defs objects must also be made strict (Azure rejects nested non-strict)."""
    schema = _to_azure_strict_schema(_NestedModel)
    defs = schema.get("$defs") or {}
    assert defs, "expected nested model to produce $defs"
    for def_name, def_schema in defs.items():
        if "properties" in def_schema:
            props = set((def_schema.get("properties") or {}).keys())
            req = set(def_schema.get("required") or [])
            assert def_schema.get("additionalProperties") is False, (
                f"$defs/{def_name} missing additionalProperties: false"
            )
            assert req == props, (
                f"$defs/{def_name} required != properties.keys(): "
                f"missing={props - req}, extra={req - props}"
            )


def test_helper_is_idempotent():
    """Running the helper on an already-strict schema must produce identical output."""
    schema_a = _to_azure_strict_schema(_OptionalFieldsModel)
    # Build a fresh model class with the SAME shape and run again
    schema_b = _to_azure_strict_schema(_OptionalFieldsModel)
    assert schema_a == schema_b


def test_helper_handles_real_contract_classification_failure_shape():
    """Regression test for the exact UAT-NEW-02 failure (live 2026-05-06 05:42:05Z).

    The Azure error called out 'effective_date' specifically. The real
    ContractClassification model has effective_date AND expiration_date as
    Optional[str] — both must end up in `required` after the helper runs.
    """
    from app.harnesses.contract_review import ContractClassification

    schema = _to_azure_strict_schema(ContractClassification)
    req = set(schema.get("required") or [])
    assert "effective_date" in req, (
        "effective_date must be in required under Azure strict mode "
        "(was not in master/c71dce2 model_json_schema output — UAT-NEW-02)"
    )
    assert "expiration_date" in req, (
        "expiration_date must be in required under Azure strict mode"
    )
    # And the other 5 fields must still be there
    expected = {
        "contract_type", "parties", "effective_date", "expiration_date",
        "governing_law", "jurisdiction", "summary",
    }
    assert req == expected, f"required={req} != expected={expected}"
