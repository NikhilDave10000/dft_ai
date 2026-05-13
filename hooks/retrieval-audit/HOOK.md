# Retrieval Audit Hook

## Purpose

Audit retrieval integrity before response generation.

## Responsibilities

- verify canonical command identity,
- verify ontology grounding,
- verify semantic chunk existence,
- verify chunk_id citations,
- detect unresolved drift,
- detect hallucinated commands.

## Validation Pipeline

1. Resolve command through canonical_commands.json.
2. Verify ontology family exists.
3. Verify semantic chunks exist.
4. Verify cited chunk_ids are real.
5. Verify commands referenced exist in registry.
6. Reject hallucinated commands.

## Failure Conditions

Fail retrieval if:
- command does not exist,
- ontology is unresolved,
- chunk source missing,
- chunk_id invalid,
- canonical drift unresolved.

## Output

Audit report:
- PASS
- WARNING
- FAIL

with:
- evidence,
- command identity,
- missing dependencies,
- drift evidence.

## Principles

- Validators observe truth.
- Validators never mutate truth.
- Drift evidence must remain observable.
