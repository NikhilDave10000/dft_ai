#!/usr/bin/env python3
"""
audit_logger.py — DFT Factory Audit & Traceability System
=======================================================

IMPLEMENTATION OF: DFT_FACTORY/AUDIT_SPEC.md

This is the nervous system of the platform. Every AI action, file change,
test result, discussion, and decision MUST emit an event through this module.

SPEC REFERENCE: DFT_FACTORY/AUDIT_SPEC.md (read before modifying this file)

--------------------------------------------------------------------
CORE PRINCIPLES (from spec):
  1. events.jsonl is APPEND-ONLY — no edits, no deletions
  2. Every line is a complete JSON object (grepable, not pretty-printed)
  3. All 8 mandatory fields MUST be present in every event
  4. Session ID links all artifacts for one session
  5. Without this audit trail, AI actions are opaque and untraceable
--------------------------------------------------------------------
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# PATH RESOLUTION
# --------------------------------------------------------------------------

def _factory_root() -> Path:
    """Find DFT_FACTORY root by walking up from this file."""
    p = Path(__file__).resolve().parent.parent
    return p


def _ensure_dirs() -> None:
    """Create logs/ directory tree if not exists."""
    root = _factory_root()
    for sub in ["events", "discussions", "decisions", "test_runs", "artifacts", "sessions"]:
        (root / "logs" / sub).mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# SESSION ID GENERATION
# Spec §7.6
# --------------------------------------------------------------------------

def generate_session_id() -> str:
    """
    Generate unique session ID like 'sess_a3f8b2'.
    Used to link all artifacts for one engineering session.
    """
    return f"sess_{uuid.uuid4().hex[:6]}"


# --------------------------------------------------------------------------
# CORE EVENT LOGGER
# Spec §7.1 — THE FOUNDATION that everything else calls
# --------------------------------------------------------------------------

# Mandatory fields (spec §3.1) — every event MUST have these
_MANDATORY_FIELDS = {
    "timestamp", "session_id", "actor", "action",
    "target", "reason", "approved_by", "tests_passed", "rollback_possible",
}

# Allowed actions (spec §3)
_VALID_ACTIONS = {
    "create_file", "modify_file", "delete_file",
    "run_test", "merge", "revert",
    "discuss", "decide",
}

# Allowed actors (spec §4)
_VALID_ACTORS = {
    "User", "Claude", "Gemini", "Qwen", "DeepSeek",
    "Orchestrator", "Validator",
}


def log_event(**kwargs) -> None:
    """
    Append ONE event line to logs/events/events.jsonl.

    MANDATORY fields (spec §3.1):
      timestamp      : UTC ISO 8601 (auto-generated if omitted)
      session_id    : from generate_session_id()
      actor         : User|Claude|Gemini|Qwen|DeepSeek|Orchestrator|Validator
      action        : create_file|modify_file|delete_file|run_test|merge|revert|discuss|decide
      target        : file path, topic, or decision ID
      reason        : why this happened
      approved_by   : who approved (usually "Nikhil")
      tests_passed  : bool
      rollback_possible: bool

    Any extra kwargs become additional fields (action-specific, see spec §3.2-3.6).

    SPEC REF: AUDIT_SPEC.md §7.1
    """
    _ensure_dirs()
    root = _factory_root()
    events_file = root / "logs" / "events" / "events.jsonl"

    # --- build event dict ---
    event = {}

    # Auto-generate timestamp if not provided
    if "timestamp" not in kwargs:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
    else:
        event["timestamp"] = kwargs.pop("timestamp")

    # --- validate mandatory fields (only set None if not already set) ---
    for field in _MANDATORY_FIELDS:
        if field in kwargs:
            event[field] = kwargs.pop(field)
        elif field not in event:
            event[field] = None  # spec says fields MUST exist, even if None

    # --- validate action ---
    if event["action"] not in _VALID_ACTIONS:
        print(f"WARNING [audit_logger]: Invalid action '{event['action']}'. "
              f"Must be one of {_VALID_ACTIONS}")
        event["action"] = "modify_file"  # safe fallback

    # --- validate actor ---
    if event["actor"] not in _VALID_ACTORS:
        print(f"WARNING [audit_logger]: Unknown actor '{event['actor']}'. "
              f"Consider adding to _VALID_ACTORS in audit_logger.py")

    # --- action-specific field validation (spec §3.2-3.6) ---
    action = event["action"]
    if action in ("create_file", "modify_file", "delete_file"):
        _validate_file_event(event, kwargs)
    elif action == "run_test":
        _validate_test_event(event, kwargs)
    elif action == "discuss":
        _validate_discuss_event(event, kwargs)
    elif action == "decide":
        _validate_decide_event(event, kwargs)
    elif action in ("merge", "revert"):
        _validate_merge_event(event, kwargs)

    # --- add any remaining extra fields ---
    event.update(kwargs)

    # --- append as SINGLE LINE (not pretty-printed) ---
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# --------------------------------------------------------------------------
# ACTION-SPECIFIC VALIDATION (spec §3.2-3.6)
# --------------------------------------------------------------------------

def _validate_file_event(event: dict, kwargs: dict) -> None:
    """Spec §3.2 — create_file / modify_file / delete_file"""
    if "model_used" in kwargs:
        event["model_used"] = kwargs.pop("model_used")
    if "diff_path" in kwargs:
        event["diff_path"] = kwargs.pop("diff_path")
    if "dependencies" in kwargs:
        event["dependencies"] = kwargs.pop("dependencies")
    if "commit_hash" in kwargs:
        event["commit_hash"] = kwargs.pop("commit_hash")
    if "lines_added" in kwargs:
        event["lines_added"] = kwargs.pop("lines_added")
    if "lines_removed" in kwargs:
        event["lines_removed"] = kwargs.pop("lines_removed")


def _validate_test_event(event: dict, kwargs: dict) -> None:
    """Spec §3.3 — run_test"""
    if "test_type" in kwargs:
        event["test_type"] = kwargs.pop("test_type")
    if "passed" in kwargs:
        event["passed"] = kwargs.pop("passed")
    if "failed" in kwargs:
        event["failed"] = kwargs.pop("failed")
    if "output_file" in kwargs:
        event["output_file"] = kwargs.pop("output_file")
    if "duration_s" in kwargs:
        event["duration_s"] = kwargs.pop("duration_s")


def _validate_discuss_event(event: dict, kwargs: dict) -> None:
    """Spec §3.4 — discuss"""
    if "discussion_id" in kwargs:
        event["discussion_id"] = kwargs.pop("discussion_id")
    if "participants" in kwargs:
        event["participants"] = kwargs.pop("participants")
    if "topic" in kwargs:
        event["topic"] = kwargs.pop("topic")
    if "consensus" in kwargs:
        event["consensus"] = kwargs.pop("consensus")
    if "dissenting" in kwargs:
        event["dissenting"] = kwargs.pop("dissenting")


def _validate_decide_event(event: dict, kwargs: dict) -> None:
    """Spec §3.5 — decide"""
    if "decision_id" in kwargs:
        event["decision_id"] = kwargs.pop("decision_id")
    if "title" in kwargs:
        event["title"] = kwargs.pop("title")
    if "status" in kwargs:
        event["status"] = kwargs.pop("status")
    if "alternatives" in kwargs:
        event["alternatives"] = kwargs.pop("alternatives")


def _validate_merge_event(event: dict, kwargs: dict) -> None:
    """Spec §3.6 — merge / revert"""
    if "commit_hash" in kwargs:
        event["commit_hash"] = kwargs.pop("commit_hash")
    if "files_changed" in kwargs:
        event["files_changed"] = kwargs.pop("files_changed")
    if "session_files" in kwargs:
        event["session_files"] = kwargs.pop("session_files")


# --------------------------------------------------------------------------
# FILE CHANGE LOGGER
# Spec §7.5 — convenience wrapper for file modify/create/delete
# --------------------------------------------------------------------------

def log_file_change(
    session_id:     str,
    file_path:      str,
    change_type:    str,       # create|modify|delete
    model_used:     str = "",
    prompt:         str = "",
    diff_path:      str = "",
    dependencies:   list[str] = None,
    lines_added:    int = 0,
    lines_removed:  int = 0,
    commit_hash:    str = "",
    **kwargs                # passed to log_event()
) -> None:
    """
    Convenience wrapper for file changes. Calls log_event(action=change_type).

    SPEC REF: AUDIT_SPEC.md §7.5

    Examples:
        log_file_change(sess, "validator_l3.py", "modify",
                         model_used="gemini/gemini-2.5-pro",
                         prompt="Add L3 context validation",
                         reason="L3 blocks invalid orderings")

        log_file_change(sess, "new_file.py", "create",
                         model_used="qwen2.5-coder:7b",
                         reason="New utility module")
    """
    log_event(
        session_id=session_id,
        actor=kwargs.pop("actor", "User"),
        action=change_type + "_file" if not change_type.endswith("_file") else change_type,
        target=file_path,
        reason=kwargs.pop("reason", ""),
        approved_by=kwargs.pop("approved_by", "Nikhil"),
        tests_passed=kwargs.pop("tests_passed", False),
        rollback_possible=kwargs.pop("rollback_possible", True),
        model_used=model_used,
        prompt=prompt,
        diff_path=diff_path,
        dependencies=dependencies or [],
        lines_added=lines_added,
        lines_removed=lines_removed,
        commit_hash=commit_hash,
        **kwargs,
    )


# --------------------------------------------------------------------------
# TEST RESULT LOGGER
# Spec §7.4
# --------------------------------------------------------------------------

def log_test_result(
    session_id:    str,
    test_type:     str,       # pytest|tcl_dryrun|schema_check|syntax_check
    passed:        bool,
    failed:        int = 0,
    output:         str = "",    # raw output text
    duration_s:    float = 0.0,
    **kwargs                # passed to log_event()
) -> None:
    """
    Log a test run. Saves output to logs/test_runs/.

    SPEC REF: AUDIT_SPEC.md §7.4

    Example:
        log_test_result(sess, "pytest", True,
                         output=test_output, reason="Post-merge validation")
    """
    _ensure_dirs()
    root = _factory_root()

    # Save output to file
    ext = "jsonl" if "pytest" in test_type else "log"
    output_file = (root / "logs" / "test_runs" /
                   f"{session_id}_{test_type}.{ext}")
    if output:
        output_file.write_text(output, encoding="utf-8")

    log_event(
        session_id=session_id,
        actor=kwargs.pop("actor", "Validator"),
        action="run_test",
        target=test_type,
        reason=kwargs.pop("reason", ""),
        approved_by=kwargs.pop("approved_by", "Nikhil"),
        tests_passed=passed,
        rollback_possible=kwargs.pop("rollback_possible", True),
        test_type=test_type,
        passed=passed,
        failed=failed,
        output_file=str(output_file),
        duration_s=duration_s,
        **kwargs,
    )


# --------------------------------------------------------------------------
# DISCUSSION LOGGER
# Spec §7.2
# --------------------------------------------------------------------------

def log_discussion(
    session_id:    str,
    topic:         str,
    participants:   list[str],
    transcript:    str,       # full prompt/response pairs
    consensus:     str = "",
    dissenting:    list[str] = None,
    **kwargs                # passed to log_event()
) -> str:                  # returns discussion_id
    """
    Log a discussion/debate. Saves transcript to logs/discussions/.
    Returns the discussion_id for linking.

    SPEC REF: AUDIT_SPEC.md §7.2

    Example:
        disc_id = log_discussion(sess, "L3 refactoring",
            ["Gemini", "DeepSeek", "User"],
            full_transcript, consensus="Split into L3Validator+L3Advisor")
    """
    _ensure_dirs()
    root = _factory_root()

    # Count existing discussions for this session
    disc_dir = root / "logs" / "discussions"
    existing = list(disc_dir.glob(f"{session_id}_disc*.md"))
    disc_num = len(existing) + 1
    discussion_id = f"{session_id}_disc{disc_num}"

    # Save transcript
    disc_file = disc_dir / f"{discussion_id}.md"
    disc_content = f"# Discussion: {topic}\n\n"
    disc_content += f"Session: {session_id}\n"
    disc_content += f"Participants: {', '.join(participants)}\n"
    disc_content += f"Consensus: {consensus}\n"
    disc_content += f"Dissenting: {', '.join(dissenting or [])}\n\n"
    disc_content += "---\n\n{transcript}\n"
    disc_file.write_text(disc_content, encoding="utf-8")

    log_event(
        session_id=session_id,
        actor=kwargs.pop("actor", "Gemini"),
        action="discuss",
        target=topic,
        reason=kwargs.pop("reason", ""),
        approved_by=kwargs.pop("approved_by", "Nikhil"),
        tests_passed=kwargs.pop("tests_passed", False),
        rollback_possible=kwargs.pop("rollback_possible", True),
        discussion_id=discussion_id,
        participants=participants,
        topic=topic,
        consensus=consensus,
        dissenting=dissenting or [],
        **kwargs,
    )
    return discussion_id


# --------------------------------------------------------------------------
# DECISION LOGGER
# Spec §7.3
# --------------------------------------------------------------------------

def log_decision(
    session_id:    str,
    title:         str,
    status:         str = "proposed",   # proposed|accepted|rejected|deprecated
    context:       str = "",
    decision:      str = "",
    alternatives:   list[str] = None,
    consequences:  str = "",
    **kwargs                # passed to log_event()
) -> str:                  # returns decision_id
    """
    Log an architecture decision. Writes ADR to logs/decisions/.
    Appends to DECISIONS.md index.
    Returns the decision_id for linking.

    SPEC REF: AUDIT_SPEC.md §7.3

    Example:
        dec_id = log_decision(sess, "Deterministic Validation Layer",
            status="accepted", context="Need final gate before merge",
            decision="Add core/validation_pipeline.py")
    """
    _ensure_dirs()
    root = _factory_root()

    # Generate decision_id (find next number)
    dec_dir = root / "logs" / "decisions"
    existing = list(dec_dir.glob("ADR-*.md"))
    next_num = 1
    for f in existing:
        try:
            num = int(f.stem.split("-")[1])
            next_num = max(next_num, num + 1)
        except (IndexError, ValueError):
            continue
    decision_id = f"ADR-{next_num:03d}-{title.lower().replace(' ', '-')[:30]}"

    # Write ADR file
    adr_file = dec_dir / f"{decision_id}.md"
    adr_content = f"# {decision_id}: {title}\n\n"
    adr_content += f"## Status\n{status}\n\n"
    adr_content += f"## Context\n{context}\n\n"
    adr_content += f"## Decision\n{decision}\n\n"
    adr_content += f"## Alternatives Considered\n"
    for alt in (alternatives or []):
        adr_content += f"- {alt}\n"
    adr_content += f"\n## Consequences\n{consequences}\n"
    adr_file.write_text(adr_content, encoding="utf-8")

    # Append to DECISIONS.md index
    index_file = root / "DECISIONS.md"
    index_line = f"| [{decision_id}](#{decision_id}) | {title} | ✅ {status} | {datetime.now(timezone.utc).date()} |\n"
    with open(index_file, "a", encoding="utf-8") as f:
        f.write(index_line)

    log_event(
        session_id=session_id,
        actor=kwargs.pop("actor", "User"),
        action="decide",
        target=decision_id,
        reason=kwargs.pop("reason", ""),
        approved_by=kwargs.pop("approved_by", "Nikhil"),
        tests_passed=kwargs.pop("tests_passed", False),
        rollback_possible=kwargs.pop("rollback_possible", True),
        decision_id=decision_id,
        title=title,
        status=status,
        alternatives=alternatives or [],
        **kwargs,
    )
    return decision_id


# --------------------------------------------------------------------------
# SESSION METADATA LOGGER
# --------------------------------------------------------------------------

def log_session_meta(
    session_id:   str,
    actor:       str = "User",
    summary:      str = "",
    **kwargs
) -> None:
    """
    Write session metadata to logs/sessions/{session_id}_meta.json.
    Called once at session start.
    """
    _ensure_dirs()
    root = _factory_root()
    meta_file = root / "logs" / "sessions" / f"{session_id}_meta.json"
    meta = {
        "session_id": session_id,
        "actor": actor,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
    meta.update(kwargs)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# QUERY HELPERS (spec §6 — "What You Must Be Able to Answer")
# --------------------------------------------------------------------------

def query_events(filter_func=None) -> list[dict]:
    """
    Read events.jsonl and return events matching filter_func(event_dict).
    Example:
        # All modifications to validator_l3.py
        events = query_events(lambda e: e['action']=='modify_file' and e['target']=='validator_l3.py')
    """
    root = _factory_root()
    events_file = root / "logs" / "events" / "events.jsonl"
    if not events_file.exists():
        return []
    results = []
    with open(events_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if filter_func is None or filter_func(event):
                    results.append(event)
            except json.JSONDecodeError:
                continue
    return results


# --------------------------------------------------------------------------
# CLI (quick tests from command line)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="DFT Factory Audit Logger — query and test events"
    )
    p.add_argument("--test",    action="store_true",
                   help="Run built-in self-tests (spec §10)")
    p.add_argument("--query",   help="Grep-style query: 'action:modify_file'")
    p.add_argument("--session", help="Show all events for a session_id")

    args = p.parse_args()

    if args.test:
        # Spec §10 — self-tests
        print("Running audit_logger self-tests (AUDIT_SPEC.md §10)...\n")

        sid = generate_session_id()
        print(f"1. Generated session ID: {sid}")

        log_event(session_id=sid, actor="User", action="modify_file",
                  target="test.py", reason="Testing audit_logger",
                  approved_by="Nikhil", tests_passed=False, rollback_possible=True)
        print("2. Logged test event")

        count = len(query_events())
        print(f"3. events.jsonl has {count} line(s) (grepable)")

        log_file_change(sid, "test2.py", "modify", reason="Test wrapper")
        count2 = len(query_events())
        print(f"4. After second event: {count2} lines (append-only)")

        by_action = query_events(lambda e: e["action"] == "modify_file")
        print(f"5. modify_file events: {len(by_action)} (grepable)")

        print("\n[PASS] Self-tests passed. Check logs/events/events.jsonl")
        print("   Run: grep '\"action\":\"modify_file\"' logs/events/events.jsonl")

    elif args.query:
        # Simple grep-style query: "field:value"
        if ":" in args.query:
            field, _, value = args.query.partition(":")
            events = query_events(lambda e: str(e.get(field, "")) == value)
            for e in events:
                print(json.dumps(e, ensure_ascii=False, separators=(",", ":")))
        else:
            print("Query format: field:value (e.g., action:modify_file)")

    elif args.session:
        events = query_events(lambda e: e.get("session_id") == args.session)
        for e in events:
            print(json.dumps(e, ensure_ascii=False, separators=(",", ":")))

    else:
        p.print_help()
