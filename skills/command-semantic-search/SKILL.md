# Command Semantic Search

## Purpose

Retrieve authoritative semantic information about DFT commands using:
- canonical command registry,
- ontology mappings,
- semantic chunks,
- parser telemetry.

## Retrieval Order

1. canonical_commands.json
2. ontology_map.json
3. semantic_chunks/*.chunks.json
4. parser telemetry logs

## Rules

- Never invent commands.
- Resolve filename drift before retrieval.
- Prefer canonical command names.
- Cite chunk_id in responses.
- Examples are execution evidence only.

## Inputs

- command name
- semantic family
- workflow role
- related command
- execution example
- syntax option

## Outputs

- canonical command identity
- semantic family
- syntax
- arguments
- execution examples
- related commands
- workflow relationships

## Retrieval Strategy

1. Resolve command identity.
2. Load canonical command metadata.
3. Load ontology family.
4. Retrieve semantic chunks.
5. Rank:
   - syntax
   - arguments
   - descriptions
   - execution examples
6. Return grounded response.

## Failure Handling

If command is unresolved:
- check canonical registry drift,
- check parser filename,
- check ontology aliases,
- report ambiguity explicitly.

Never hallucinate missing commands.
