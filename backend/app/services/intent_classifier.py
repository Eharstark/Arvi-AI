"""
services/intent_classifier.py — Intent Classification Engine
=============================================================
Determines whether a user's message is SIMPLE or COMPLEX.

SIMPLE  → Standard Q&A, greetings, quick questions
          Handled directly by Gemini — reply immediately

COMPLEX → Multi-step tasks, code generation, analysis, automation
          Flagged with [ESCALATE_TO_AGENT] signal for future agent routing

Why classify intent?
  This is the foundation of agentic architecture.
  Phase 1 (now):   Flag complex requests, return escalation message
  Phase 2 (future): Route to specialized agents (LangGraph, CrewAI)
  Phase 3 (future): Tool calling, web search, code execution per intent

Current method: Regex pattern matching — zero cost, zero latency.
Upgrade path:   Replace classify_intent() with a Gemini API call
                that classifies intent as part of a structured output response.
"""

import re
from app.models.chat_models import IntentType
from app.utils.helpers import log_info


# ---------------------------------------------------------------------------
# Complex Intent Patterns
# ---------------------------------------------------------------------------
# Each pattern targets a category of requests that go beyond simple Q&A.
# Patterns use word boundary \b to avoid false positives (e.g., "create" in "recreate").

COMPLEX_PATTERNS = [
    # ── Software / Application Development ───────────────────────────────
    r"\b(build|create|develop|generate|write|implement|code|program|make)\b.{0,40}\b(app|application|website|web app|api|backend|frontend|script|bot|system|tool|platform|service|pipeline|workflow|dashboard|database)\b",

    # ── Data Analysis & Research ──────────────────────────────────────────
    r"\b(analyze|analyse|research|investigate|audit|review|examine)\b.{0,30}\b(dataset|data|codebase|repository|repo|report|document|file|logs|metrics|analytics)\b",

    # ── Automation & Orchestration ────────────────────────────────────────
    r"\b(automate|automat|orchestrate|integrate|connect|sync|schedule)\b",
    r"\b(workflow|pipeline|ci\/cd|devops|multi.?step|end.?to.?end)\b",

    # ── Architecture & System Design ─────────────────────────────────────
    r"\b(architect|design|plan|roadmap|strategy|specification|diagram|structure)\b.{0,30}\b(system|application|api|database|service|infrastructure)\b",

    # ── Complex Generation ────────────────────────────────────────────────
    r"\b(write|generate|create).{0,20}\b(detailed|comprehensive|full|complete|production.?ready|end.?to.?end)\b",
    r"\b(essay|thesis|proposal|specification|documentation|technical report|white paper)\b",

    # ── Machine Learning & Data Science ──────────────────────────────────
    r"\b(machine learning|deep learning|neural network|train a model|fine.?tun|ml model|ai model)\b",
    r"\b(data science|statistics|regression|classification|clustering|nlp|computer vision)\b",

    # ── Debugging Complex Issues ──────────────────────────────────────────
    r"\b(debug|troubleshoot|diagnose|fix).{0,30}\b(entire|whole|full|production|complex|critical)\b",
    r"\b(memory leak|performance issue|race condition|deadlock|sql injection|security vulnerability)\b",

    # ── Business / Legal / Financial ─────────────────────────────────────
    r"\b(legal|contract|compliance|regulatory|financial model|forecast|valuation|due diligence)\b",

    # ── Explicit Agent / Human Request ───────────────────────────────────
    r"\b(speak to|talk to|connect me with|transfer me|escalate|human agent|live agent|specialist|expert)\b",

    # ── Long Multi-part Questions ─────────────────────────────────────────
    # Handled separately via length check in classify_intent()
]

# Compile all patterns once at module load (significant performance gain)
_compiled_patterns = [
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in COMPLEX_PATTERNS
]

# Long message threshold (characters) — very long messages are likely complex tasks
COMPLEX_LENGTH_THRESHOLD = 400


# ---------------------------------------------------------------------------
# Main Classification Function
# ---------------------------------------------------------------------------

def classify_intent(message: str) -> IntentType:
    """
    Classify a user's message as SIMPLE or COMPLEX.

    Classification algorithm (in priority order):
      1. Length check — messages over 400 chars are often complex tasks
      2. Pattern matching — regex against known complex-task indicators
      3. Default — SIMPLE if no signals detected

    Args:
        message: The cleaned, sanitized user message.

    Returns:
        IntentType.SIMPLE or IntentType.COMPLEX
    """
    # Check 1: Message length (long = likely a task, not a question)
    if len(message) > COMPLEX_LENGTH_THRESHOLD:
        log_info(f"Intent: COMPLEX (length={len(message)} > {COMPLEX_LENGTH_THRESHOLD})")
        return IntentType.COMPLEX

    # Check 2: Pattern matching against complex-task indicators
    for pattern in _compiled_patterns:
        match = pattern.search(message)
        if match:
            log_info(
                f"Intent: COMPLEX | matched='{match.group()[:50]}' "
                f"| pattern='{pattern.pattern[:50]}...'"
            )
            return IntentType.COMPLEX

    # Default: simple Q&A
    log_info(f"Intent: SIMPLE (no complex signals in '{message[:60]}...')")
    return IntentType.SIMPLE


def should_escalate(intent: IntentType) -> bool:
    """
    Determine if a classified intent should trigger escalation.

    Currently: all COMPLEX intents escalate.

    Future nuance:
      - COMPLEX + "write an essay" → Gemini can handle it, don't escalate
      - COMPLEX + "book a meeting" → needs tool use, do escalate
      - COMPLEX + "run this code"  → needs code sandbox agent, do escalate
    """
    return intent == IntentType.COMPLEX


def get_escalation_reply() -> str:
    """
    The message returned to the user when their request is escalated.

    [ESCALATE_TO_AGENT] is a machine-readable tag the frontend or
    orchestration layer can detect to trigger special UI or routing logic.

    Customize this message to match your product's voice.
    """
    return (
        "[ESCALATE_TO_AGENT] Your request involves a complex, multi-step task "
        "that benefits from specialized handling. I'm routing you to an advanced "
        "AI agent that can assist with this more effectively. "
        "Please hold on — this will just take a moment. 🔄"
    )