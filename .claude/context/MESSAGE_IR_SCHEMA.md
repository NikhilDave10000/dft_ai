# MESSAGE IR SCHEMA

## Core Fields

- message_id
- message_text
- severity
- description
- what_next

## Optional Fields

- examples
- related_commands
- related_messages
- source_file
- document_namespace

## Semantic Goals

The message IR should support:
- runtime diagnosis
- remediation guidance
- retrieval augmentation
- semantic graph linking
- command-to-error relationships

## Parsing Strategy

Messages are parsed from:
tmax_messages/

Primary semantic anchors:
- Message Text
- Severity
- Description
- What Next
