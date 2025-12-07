#!/usr/bin/env python3
"""
Obsidian Mind Map Pipeline - Phase 1
=====================================

Ingests conversation exports from inbox folders, extracts structured
knowledge using Claude API, and outputs to staging folder.

Usage:
    python pipeline.py                    # Process all new files
    python pipeline.py --file path/to/file.txt  # Process single file
    python pipeline.py --dry-run          # Show what would be processed
"""

import os
import json
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional
import anthropic

from prompts.extraction_prompt import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt
)

# ============================================================================
# CONFIGURATION - Update these paths for your system
# ============================================================================

CONFIG = {
    # Base path to your Obsidian vault
    "vault_path": Path.home() / "ObsidianVault",  # Update this!
    
    # Inbox folders for each source (relative to vault)
    "inbox_paths": {
        "claude": "00-Inbox/claude",
        "chatgpt": "00-Inbox/chatgpt", 
        "gemini": "00-Inbox/gemini",
    },
    
    # Output paths (relative to vault)
    "staging_path": "01-Processed",
    "themes_path": "02-Themes",
    "decisions_path": "03-Decisions",
    "actions_path": "04-Actions",
    "conflicts_path": "05-Conflicts",
    "bibles_path": "06-Bibles",
    "meta_path": "_meta",
    
    # Bible files to inject as context (relative to vault)
    "bible_files": [
        "06-Bibles/Gumroad_Launch_Bible.md",
        # Add more as needed
    ],
    
    # Claude API model
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 4096,
}


# ============================================================================
# PROCESSING LOG - Track what's been processed
# ============================================================================

def get_processing_log_path() -> Path:
    return CONFIG["vault_path"] / CONFIG["meta_path"] / "processing_log.json"


def load_processing_log() -> dict:
    """Load the processing log or create empty one."""
    log_path = get_processing_log_path()
    if log_path.exists():
        with open(log_path, "r") as f:
            return json.load(f)
    return {"processed_files": {}, "last_run": None}


def save_processing_log(log: dict):
    """Save the processing log."""
    log_path = get_processing_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as f:
        json.dump(log, f, indent=2, default=str)


def get_file_hash(filepath: Path) -> str:
    """Get hash of file contents for change detection."""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# ============================================================================
# INGESTION - Find and read conversation files
# ============================================================================

def find_new_files(log: dict) -> list[dict]:
    """Scan inbox folders for new or modified files."""
    new_files = []
    
    for source, inbox_rel_path in CONFIG["inbox_paths"].items():
        inbox_path = CONFIG["vault_path"] / inbox_rel_path
        
        if not inbox_path.exists():
            print(f"  Creating inbox: {inbox_path}")
            inbox_path.mkdir(parents=True, exist_ok=True)
            continue
            
        for filepath in inbox_path.glob("*.txt"):
            file_hash = get_file_hash(filepath)
            file_key = str(filepath)
            
            # Skip if already processed with same hash
            if file_key in log["processed_files"]:
                if log["processed_files"][file_key]["hash"] == file_hash:
                    continue
                    
            new_files.append({
                "path": filepath,
                "source": source,
                "hash": file_hash,
            })
    
    return new_files


def read_conversation(filepath: Path) -> str:
    """Read conversation file contents."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def parse_source_date(filepath: Path) -> str:
    """Extract date from filename or use file modified date.
    
    Expected filename formats:
    - 2024-12-07-topic-name.txt
    - topic-name.txt (falls back to file date)
    """
    filename = filepath.stem
    
    # Try to extract date from filename
    parts = filename.split("-")
    if len(parts) >= 3:
        try:
            year, month, day = parts[0], parts[1], parts[2]
            if len(year) == 4 and len(month) == 2 and len(day) == 2:
                return f"{year}-{month}-{day}"
        except (ValueError, IndexError):
            pass
    
    # Fall back to file modification time
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
    return mtime.strftime("%Y-%m-%d")


# ============================================================================
# NORMALIZATION - Convert different formats to common structure
# ============================================================================

def normalize_claude_export(text: str) -> str:
    """Normalize Claude conversation export.
    
    Claude copy/paste format is usually clean already.
    This handles any quirks we discover.
    """
    # Remove any leading/trailing whitespace
    text = text.strip()
    
    # Normalize line endings
    text = text.replace("\r\n", "\n")
    
    return text


def normalize_chatgpt_export(text: str) -> str:
    """Normalize ChatGPT conversation export.
    
    ChatGPT JSON export format:
    {
      "title": "...",
      "mapping": {
        "id": {
          "message": {
            "content": {"parts": ["..."]}
          }
        }
      }
    }
    """
    try:
        data = json.loads(text)
        
        # Extract messages from ChatGPT JSON format
        messages = []
        if "mapping" in data:
            for node_id, node in data["mapping"].items():
                if node.get("message"):
                    msg = node["message"]
                    role = msg.get("author", {}).get("role", "unknown")
                    content = msg.get("content", {})
                    
                    if isinstance(content, dict) and "parts" in content:
                        text_parts = [p for p in content["parts"] if isinstance(p, str)]
                        if text_parts:
                            messages.append(f"{role.upper()}: {' '.join(text_parts)}")
        
        return "\n\n".join(messages) if messages else text
        
    except json.JSONDecodeError:
        # Not JSON, treat as plain text
        return text.strip()


def normalize_gemini_export(text: str) -> str:
    """Normalize Gemini conversation export.
    
    Gemini doesn't have a clean export, so this handles copy/paste.
    """
    return text.strip()


def normalize_conversation(text: str, source: str) -> str:
    """Route to appropriate normalizer based on source."""
    normalizers = {
        "claude": normalize_claude_export,
        "chatgpt": normalize_chatgpt_export,
        "gemini": normalize_gemini_export,
    }
    
    normalizer = normalizers.get(source, lambda x: x.strip())
    return normalizer(text)


# ============================================================================
# CONTEXT INJECTION - Load Bible files for context
# ============================================================================

def load_bible_context() -> str:
    """Load all Bible files and concatenate for context."""
    context_parts = []
    
    for bible_rel_path in CONFIG["bible_files"]:
        bible_path = CONFIG["vault_path"] / bible_rel_path
        
        if bible_path.exists():
            with open(bible_path, "r", encoding="utf-8") as f:
                content = f.read()
                context_parts.append(f"### {bible_path.name}\n{content}")
        else:
            print(f"  Warning: Bible file not found: {bible_path}")
    
    return "\n\n---\n\n".join(context_parts) if context_parts else ""


# ============================================================================
# EXTRACTION - Call Claude API to extract knowledge
# ============================================================================

def extract_knowledge(
    conversation_text: str,
    source: str,
    source_date: str,
    bible_context: str,
    client: anthropic.Anthropic
) -> dict:
    """Send conversation to Claude API and get structured extraction."""
    
    user_prompt = build_extraction_prompt(
        conversation_text=conversation_text,
        source=source,
        source_date=source_date,
        bible_context=bible_context
    )
    
    response = client.messages.create(
        model=CONFIG["model"],
        max_tokens=CONFIG["max_tokens"],
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    
    # Extract text from response
    response_text = response.content[0].text
    
    # Parse JSON response
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"  Error parsing API response: {e}")
        print(f"  Raw response: {response_text[:500]}...")
        return {"items": [], "error": str(e)}


# ============================================================================
# OUTPUT - Write extracted items to staging folder
# ============================================================================

def generate_item_id(item: dict, source: str, source_date: str) -> str:
    """Generate unique ID for an extracted item."""
    content = f"{item['type']}-{item['title']}-{source}-{source_date}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def format_frontmatter(metadata: dict) -> str:
    """Format YAML frontmatter for Obsidian note."""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}: {json.dumps(value)}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def write_staged_item(
    item: dict,
    source: str,
    source_date: str,
    source_file: str,
    staging_dir: Path
):
    """Write a single extracted item to staging folder."""
    
    item_id = generate_item_id(item, source, source_date)
    item_type = item["type"]
    
    # Create filename
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in item["title"])
    safe_title = safe_title.replace(" ", "-").lower()[:50]
    filename = f"{item_type}-{safe_title}-{item_id}.md"
    
    # Build frontmatter
    frontmatter = format_frontmatter({
        "title": item["title"],
        "type": item_type,
        "source": source,
        "source_date": source_date,
        "source_file": source_file,
        "related_themes": item.get("related_themes", []),
        "confidence": item.get("confidence", "medium"),
        "status": "staged",
        "created": datetime.now().isoformat(),
        "id": item_id,
    })
    
    # Build content
    content = f"""{frontmatter}

# {item["title"]}

{item["content"]}

## Key Quote
> {item.get("key_quote", "No quote captured")}

## Review Notes
_Add your notes here when reviewing this item._

## Actions
- [ ] Review and route to appropriate folder
"""
    
    # Write file
    filepath = staging_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    return filepath


def write_extraction_summary(
    extraction: dict,
    source: str,
    source_date: str,
    source_file: str,
    staging_dir: Path
):
    """Write a summary file for the extraction batch."""
    
    summary_filename = f"_summary-{source}-{source_date}.md"
    
    items_by_type = {}
    for item in extraction.get("items", []):
        item_type = item["type"]
        if item_type not in items_by_type:
            items_by_type[item_type] = []
        items_by_type[item_type].append(item["title"])
    
    content = f"""---
type: extraction-summary
source: {source}
source_date: {source_date}
source_file: {source_file}
processed_at: {datetime.now().isoformat()}
item_count: {len(extraction.get("items", []))}
---

# Extraction Summary: {source} ({source_date})

## Conversation Summary
{extraction.get("conversation_summary", "No summary available")}

## Primary Themes
{chr(10).join(f"- {t}" for t in extraction.get("primary_themes", []))}

## Extracted Items

"""
    
    for item_type, titles in items_by_type.items():
        content += f"### {item_type.title()}s ({len(titles)})\n"
        for title in titles:
            content += f"- {title}\n"
        content += "\n"
    
    filepath = staging_dir / summary_filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def process_file(
    file_info: dict,
    bible_context: str,
    client: anthropic.Anthropic,
    dry_run: bool = False
) -> bool:
    """Process a single conversation file."""
    
    filepath = file_info["path"]
    source = file_info["source"]
    
    print(f"\n  Processing: {filepath.name}")
    
    # Read and normalize
    raw_text = read_conversation(filepath)
    normalized_text = normalize_conversation(raw_text, source)
    source_date = parse_source_date(filepath)
    
    print(f"    Source: {source}, Date: {source_date}")
    print(f"    Length: {len(normalized_text):,} characters")
    
    if dry_run:
        print("    [DRY RUN] Would extract and write to staging")
        return True
    
    # Extract knowledge
    print("    Extracting knowledge via API...")
    extraction = extract_knowledge(
        conversation_text=normalized_text,
        source=source,
        source_date=source_date,
        bible_context=bible_context,
        client=client
    )
    
    if "error" in extraction:
        print(f"    Error: {extraction['error']}")
        return False
    
    items = extraction.get("items", [])
    print(f"    Extracted {len(items)} items")
    
    # Create staging directory for today
    staging_dir = CONFIG["vault_path"] / CONFIG["staging_path"] / source_date
    staging_dir.mkdir(parents=True, exist_ok=True)
    
    # Write items
    for item in items:
        item_path = write_staged_item(
            item=item,
            source=source,
            source_date=source_date,
            source_file=str(filepath.relative_to(CONFIG["vault_path"])),
            staging_dir=staging_dir
        )
        print(f"      → {item_path.name}")
    
    # Write summary
    summary_path = write_extraction_summary(
        extraction=extraction,
        source=source,
        source_date=source_date,
        source_file=str(filepath.relative_to(CONFIG["vault_path"])),
        staging_dir=staging_dir
    )
    print(f"      → {summary_path.name}")
    
    return True


def run_pipeline(dry_run: bool = False, single_file: Optional[str] = None):
    """Run the full pipeline."""
    
    print("=" * 60)
    print("Obsidian Mind Map Pipeline - Phase 1")
    print("=" * 60)
    
    # Initialize API client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not dry_run:
        print("\nError: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        return
    
    client = anthropic.Anthropic(api_key=api_key) if api_key else None
    
    # Load processing log
    log = load_processing_log()
    print(f"\nLast run: {log.get('last_run', 'Never')}")
    
    # Load Bible context
    print("\nLoading Bible context...")
    bible_context = load_bible_context()
    if bible_context:
        print(f"  Loaded {len(CONFIG['bible_files'])} Bible file(s)")
    else:
        print("  No Bible files loaded (continuing without context)")
    
    # Find files to process
    if single_file:
        filepath = Path(single_file)
        if not filepath.exists():
            print(f"\nError: File not found: {single_file}")
            return
        
        # Determine source from path
        source = "unknown"
        for src, inbox_path in CONFIG["inbox_paths"].items():
            if inbox_path in str(filepath):
                source = src
                break
        
        new_files = [{
            "path": filepath,
            "source": source,
            "hash": get_file_hash(filepath),
        }]
    else:
        print("\nScanning inbox folders...")
        new_files = find_new_files(log)
    
    if not new_files:
        print("  No new files to process")
        return
    
    print(f"  Found {len(new_files)} file(s) to process")
    
    # Process each file
    success_count = 0
    for file_info in new_files:
        success = process_file(
            file_info=file_info,
            bible_context=bible_context,
            client=client,
            dry_run=dry_run
        )
        
        if success and not dry_run:
            # Update processing log
            log["processed_files"][str(file_info["path"])] = {
                "hash": file_info["hash"],
                "processed_at": datetime.now().isoformat(),
                "source": file_info["source"],
            }
            success_count += 1
    
    # Save log
    if not dry_run:
        log["last_run"] = datetime.now().isoformat()
        save_processing_log(log)
    
    print("\n" + "=" * 60)
    print(f"Complete! Processed {success_count}/{len(new_files)} files")
    print(f"Staged items in: {CONFIG['vault_path'] / CONFIG['staging_path']}")
    print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process conversation exports into Obsidian knowledge items"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process a single file instead of scanning inbox"
    )
    
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run, single_file=args.file)
