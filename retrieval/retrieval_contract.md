# Semantic Retrieval Contract

## Purpose

Define deterministic retrieval behavior for the DFT AI system.

Retrieval is authoritative memory access.
Generation is secondary.

---

## Retrieval Sources

Priority order:

1. canonical_commands.json
2. ontology_map.json
3. semantic_chunks/
4. parser telemetry
5. validator telemetry

---

## Retrieval Units

The authoritative retrieval unit is:

semantic chunk

NOT:
- raw HTML,
- parser text blobs,
- arbitrary token windows.

---

## Mandatory Retrieval Sequence

### 1. Resolve Identity

Resolve:
- canonical command,
- filename drift,
- aliases.

Source:
- canonical registry

---

### 2. Resolve Ontology

Resolve:
- semantic family,
- workflow role,
- related commands.

Source:
- ontology map

---

### 3. Retrieve Semantic Chunks

Chunk priority:

1. syntax
2. arguments
3. short_description
4. description
5. execution_example

---

### 4. Validate Retrieval

Validate:
- chunk existence,
- ontology grounding,
- chunk_id integrity,
- command integrity.

---

## Response Requirements

Responses must:
- cite chunk_id,
- preserve canonical command identity,
- distinguish syntax from examples,
- preserve execution semantics.

---

## Forbidden Behavior

Never:
- invent commands,
- infer undocumented arguments,
- merge syntax with examples,
- silently normalize drift,
- retrieve raw parser blobs directly.

---

## Retrieval Philosophy

Retrieval is:
- deterministic,
- ontology-grounded,
- canonicalized,
- auditable,
- validator-aware.
