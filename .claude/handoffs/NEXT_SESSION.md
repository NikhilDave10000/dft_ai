# NEXT SESSION

## Current Priority

Stabilize namespace-aware document classification before parser router implementation.

## Immediate Next Task

Refactor document_classifier.py:
- classify by namespace first
- apply filename heuristics second
- eliminate global .htm → COMMAND_PAGE fallback

## Current Known Problem

COMMAND_PAGE count is inflated because semantic fallback is too aggressive across the entire corpus.

## Expected Result After Fix

Approximate topology:
- COMMAND_PAGE ≈ 244
- GUIDE_PAGE = realistic
- DRC_RULE = realistic
- MESSAGE_REF = realistic

## After Classification Stabilization

Next major milestone:
- parser_router.py
- typed parser dispatch
- multi-corpus semantic ingestion
