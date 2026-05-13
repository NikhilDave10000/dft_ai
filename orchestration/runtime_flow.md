# DFT AI Runtime Flow

## High-Level Runtime Architecture

User Query
    ↓
Command Resolution
    ↓
Canonical Registry Lookup
    ↓
Ontology Resolution
    ↓
Skill Selection
    ↓
Agent Selection
    ↓
Semantic Retrieval
    ↓
Retrieval Audit Hook
    ↓
Grounded Response Generation
    ↓
Telemetry Logging

---

## Resolution Pipeline

### 1. Command Resolution

Resolve:
- canonical command identity,
- filename drift,
- aliases,
- parser naming inconsistencies.

Source:
- canonical_commands.json

---

### 2. Ontology Resolution

Resolve:
- semantic family,
- workflow role,
- command relationships.

Source:
- ontology_map.json

---

### 3. Skill Routing

Select appropriate skill:
- command-semantic-search,
- timing-analysis,
- diagnosis-triage,
- scan-chain-analysis,
- ATPG-debugging.

---

### 4. Agent Routing

Select reasoning persona:
- DFT command expert,
- diagnosis expert,
- ATPG analyst,
- scan-chain debugger.

---

### 5. Semantic Retrieval

Retrieve:
- syntax,
- arguments,
- descriptions,
- execution examples,
- workflow relationships.

Source:
- semantic_chunks/

---

### 6. Retrieval Audit

Validate:
- chunk existence,
- canonical identity,
- ontology grounding,
- citation integrity,
- hallucination detection.

Source:
- retrieval-audit hook

---

### 7. Response Generation

Generate:
- grounded,
- ontology-aware,
- chunk-cited,
- deterministic response.

Never:
- hallucinate commands,
- infer undocumented syntax,
- silently normalize drift.

---

## Core Principles

- Identity before semantics.
- Ontology before inference.
- Retrieval before generation.
- Validation before response.
- Observability before automation.
