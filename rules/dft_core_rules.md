# DFT Core Rules

## Command Integrity

- Never invent commands.
- Commands must exist in canonical_commands.json.
- Filename drift must be resolved via canonical registry.
- Canonical command identity is authoritative.

## Ontology Integrity

- Ontology mapping is authoritative.
- Semantic family must never be inferred.
- Parser telemetry must not override ontology truth.

## Retrieval Integrity

- Retrieval responses must cite chunk_id.
- Semantic chunks are authoritative retrieval units.
- Examples are execution evidence, not syntax definitions.

## Parsing Integrity

- Parser telemetry is authoritative debugging evidence.
- Embedded PRE blocks must preserve execution semantics.
- Validators detect inconsistencies; they do not mutate truth.

## Safety

- Never silently normalize semantic meaning.
- Never auto-correct command names without registry evidence.
- Drift evidence must always remain observable.
