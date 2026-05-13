# ARCHITECTURE

## Core Semantic Pipeline

1. Document Classification
   - namespace-aware corpus classification
   - semantic type detection

2. Canonical Registry
   - command identity resolution
   - filename ↔ canonical mapping
   - drift preservation

3. Parsing Layer
   - command parser
   - future parser router
   - future guide/rule/message parsers

4. Semantic IR
   - normalized semantic representation
   - telemetry stripped from parser outputs

5. Ontology Layer
   - semantic family mapping
   - command relationship structure

6. Semantic Chunking
   - syntax chunks
   - argument chunks
   - description chunks
   - example chunks

7. Validation Layer
   - canonical integrity
   - ontology coverage
   - semantic chunk validation
   - parser structure validation
   - cross-field consistency validation

8. Future Graph Layer
   - semantic graph
   - command relationships
   - workflow topology
   - retrieval augmentation
