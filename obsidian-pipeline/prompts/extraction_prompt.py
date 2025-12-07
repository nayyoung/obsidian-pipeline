"""
Extraction Prompt for Obsidian Mind Map Pipeline

This prompt is sent to Claude API along with the conversation text
and any Bible context. It returns structured JSON for downstream processing.
"""

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction assistant. Your job is to analyze conversation transcripts and extract structured insights for a personal knowledge management system.

The user maintains an Obsidian vault with interconnected notes. Your extractions will become nodes in their knowledge graph.

CRITICAL RULES:
1. Extract ONLY what was actually discussed—never invent or extrapolate
2. Every item needs a key_quote that can be searched to find the original conversation
3. Related themes should use [[Wiki Link]] syntax for Obsidian compatibility
4. Be selective—quality over quantity. 3 good insights beats 10 mediocre ones
5. Confidence levels matter: "high" = explicitly stated, "medium" = strongly implied, "low" = loosely connected

OUTPUT FORMAT: Return valid JSON only. No markdown code blocks, no explanations."""


EXTRACTION_USER_PROMPT = """Analyze this conversation and extract knowledge items.

## Current Context (User's Project Bible)
{bible_context}

## Conversation to Analyze
Source: {source}
Date: {source_date}

{conversation_text}

---

Extract the following item types:

**THEMES**: Recurring topics, concepts, or areas of focus. These become hub nodes in the knowledge graph.
- Only extract if discussed substantively (not just mentioned in passing)
- Link to related existing themes if obvious

**DECISIONS**: Explicit choices made or conclusions reached during the conversation.
- Must be something the user decided, not just discussed
- Include the reasoning if provided

**ACTIONS**: Concrete next steps or tasks that emerged.
- Must be actionable (has a clear "done" state)
- Include context on why it matters

**INSIGHTS**: Realizations, reframes, or valuable observations.
- Things that shifted understanding or perspective
- Non-obvious connections or implications

Return this exact JSON structure:
{{
  "items": [
    {{
      "type": "theme|decision|action|insight",
      "title": "Short descriptive title (3-7 words)",
      "content": "2-4 sentence explanation of the item",
      "key_quote": "Exact quote from conversation for search-back (15-40 words)",
      "related_themes": ["[[Theme Name]]", "[[Another Theme]]"],
      "confidence": "high|medium|low"
    }}
  ],
  "conversation_summary": "1-2 sentence summary of what this conversation was about",
  "primary_themes": ["[[Main Theme 1]]", "[[Main Theme 2]]"]
}}

Be selective. A typical conversation should yield 3-8 items total, not 15+."""


def build_extraction_prompt(
    conversation_text: str,
    source: str,
    source_date: str,
    bible_context: str = ""
) -> str:
    """Build the complete user prompt for extraction."""
    return EXTRACTION_USER_PROMPT.format(
        bible_context=bible_context if bible_context else "(No project context provided)",
        source=source,
        source_date=source_date,
        conversation_text=conversation_text
    )
