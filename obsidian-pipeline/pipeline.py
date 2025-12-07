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
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import anthropic

from prompts.extraction_prompt import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_prompt
)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

MAX_FILENAME_LENGTH = 50
ITEM_ID_LENGTH = 12
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 2  # seconds

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


def load_processing_log() -> Dict[str, Any]:
    """Load the processing log or create empty one."""
    log_path = get_processing_log_path()
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load processing log: {e}")
            logger.warning("Starting with empty processing log")
    return {"processed_files": {}, "last_run": None}


def save_processing_log(log: Dict[str, Any]) -> None:
    """Save the processing log."""
    log_path = get_processing_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            json.dump(log, f, indent=2, default=str)
    except (IOError, OSError) as e:
        logger.error(f"Failed to save processing log: {e}")
        raise


def get_file_hash(filepath: Path) -> str:
    """Get hash of file contents for change detection using SHA-256."""
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except (IOError, OSError) as e:
        logger.error(f"Failed to read file {filepath}: {e}")
        raise


# ============================================================================
# INGESTION - Find and read conversation files
# ============================================================================

def find_new_files(log: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Scan inbox folders for new or modified files."""
    new_files = []
    
    for source, inbox_rel_path in CONFIG["inbox_paths"].items():
        inbox_path = CONFIG["vault_path"] / inbox_rel_path
        
        if not inbox_path.exists():
            logger.info(f"Creating inbox: {inbox_path}")
            try:
                inbox_path.mkdir(parents=True, exist_ok=True)
            except (IOError, OSError) as e:
                logger.error(f"Failed to create inbox directory {inbox_path}: {e}")
                continue
            continue
            
        try:
            for filepath in inbox_path.glob("*.txt"):
                try:
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
                except (IOError, OSError) as e:
                    logger.warning(f"Skipping file {filepath}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error scanning inbox {inbox_path}: {e}")
            continue
    
    return new_files


def read_conversation(filepath: Path) -> str:
    """Read conversation file contents."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except (IOError, OSError, UnicodeDecodeError) as e:
        logger.error(f"Failed to read conversation file {filepath}: {e}")
        raise


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
                # Validate it's actually a valid date
                date_str = f"{year}-{month}-{day}"
                datetime.strptime(date_str, "%Y-%m-%d")
                return date_str
        except (ValueError, IndexError):
            pass
    
    # Fall back to file modification time
    try:
        mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
        return mtime.strftime("%Y-%m-%d")
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to get file modification time for {filepath}: {e}")
        # Ultimate fallback to current date
        return datetime.now().strftime("%Y-%m-%d")


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
            try:
                with open(bible_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    context_parts.append(f"### {bible_path.name}\n{content}")
            except (IOError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read Bible file {bible_path}: {e}")
        else:
            logger.warning(f"Bible file not found: {bible_path}")
    
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
) -> Dict[str, Any]:
    """Send conversation to Claude API and get structured extraction with retry logic."""
    
    user_prompt = build_extraction_prompt(
        conversation_text=conversation_text,
        source=source,
        source_date=source_date,
        bible_context=bible_context
    )
    
    last_error = None
    for attempt in range(API_RETRY_ATTEMPTS):
        try:
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
                logger.error(f"Error parsing API response: {e}")
                logger.debug(f"Raw response: {response_text[:500]}...")
                return {"items": [], "error": f"JSON decode error: {str(e)}"}
                
        except anthropic.APIError as e:
            last_error = e
            logger.warning(f"API error (attempt {attempt + 1}/{API_RETRY_ATTEMPTS}): {e}")
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(API_RETRY_DELAY * (attempt + 1))  # Exponential backoff
            continue
        except Exception as e:
            logger.error(f"Unexpected error calling API: {e}")
            return {"items": [], "error": f"Unexpected error: {str(e)}"}
    
    # All retries failed
    logger.error(f"API call failed after {API_RETRY_ATTEMPTS} attempts")
    return {"items": [], "error": f"API error after retries: {str(last_error)}"}


# ============================================================================
# OUTPUT - Write extracted items to staging folder
# ============================================================================

def generate_item_id(item: Dict[str, Any], source: str, source_date: str) -> str:
    """Generate unique ID for an extracted item using SHA-256."""
    content = f"{item['type']}-{item['title']}-{source}-{source_date}"
    return hashlib.sha256(content.encode()).hexdigest()[:ITEM_ID_LENGTH]


def format_frontmatter(metadata: Dict[str, Any]) -> str:
    """Format YAML frontmatter for Obsidian note."""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}: {json.dumps(value)}")
        elif isinstance(value, str):
            # Escape special characters in strings for YAML
            escaped_value = value.replace('"', '\\"')
            lines.append(f'{key}: "{escaped_value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def sanitize_filename(text: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """Sanitize text for safe filename usage, preventing path traversal."""
    # Remove any path separators and null bytes
    safe_text = text.replace("/", "-").replace("\\", "-").replace("\0", "")
    # Keep only alphanumeric, spaces, hyphens, and underscores
    safe_text = "".join(c if c.isalnum() or c in " -_" else "" for c in safe_text)
    # Replace spaces with hyphens and convert to lowercase
    safe_text = safe_text.replace(" ", "-").lower()
    # Remove multiple consecutive hyphens
    while "--" in safe_text:
        safe_text = safe_text.replace("--", "-")
    # Trim to max length
    safe_text = safe_text[:max_length].strip("-")
    # Ensure we have at least something
    return safe_text if safe_text else "unnamed"

def write_staged_item(
    item: Dict[str, Any],
    source: str,
    source_date: str,
    source_file: str,
    staging_dir: Path
) -> Path:
    """Write a single extracted item to staging folder."""
    
    item_id = generate_item_id(item, source, source_date)
    item_type = item["type"]
    
    # Create safe filename
    safe_title = sanitize_filename(item["title"])
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
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except (IOError, OSError) as e:
        logger.error(f"Failed to write staged item {filepath}: {e}")
        raise
    
    return filepath


def write_extraction_summary(
    extraction: Dict[str, Any],
    source: str,
    source_date: str,
    source_file: str,
    staging_dir: Path
) -> Path:
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
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except (IOError, OSError) as e:
        logger.error(f"Failed to write extraction summary {filepath}: {e}")
        raise
    
    return filepath


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def validate_file_path(filepath: Path, vault_path: Path) -> bool:
    """Validate that file path is within vault directory to prevent path traversal."""
    try:
        resolved_file = filepath.resolve()
        resolved_vault = vault_path.resolve()
        return str(resolved_file).startswith(str(resolved_vault))
    except (OSError, RuntimeError):
        return False

def process_file(
    file_info: Dict[str, Any],
    bible_context: str,
    client: anthropic.Anthropic,
    dry_run: bool = False
) -> bool:
    """Process a single conversation file."""
    
    filepath = file_info["path"]
    source = file_info["source"]
    
    logger.info(f"Processing: {filepath.name}")
    
    try:
        # Read and normalize
        raw_text = read_conversation(filepath)
        normalized_text = normalize_conversation(raw_text, source)
        source_date = parse_source_date(filepath)
        
        logger.info(f"  Source: {source}, Date: {source_date}")
        logger.info(f"  Length: {len(normalized_text):,} characters")
        
        if dry_run:
            logger.info("  [DRY RUN] Would extract and write to staging")
            return True
        
        # Extract knowledge
        logger.info("  Extracting knowledge via API...")
        extraction = extract_knowledge(
            conversation_text=normalized_text,
            source=source,
            source_date=source_date,
            bible_context=bible_context,
            client=client
        )
        
        if "error" in extraction:
            logger.error(f"  Extraction error: {extraction['error']}")
            return False
        
        items = extraction.get("items", [])
        logger.info(f"  Extracted {len(items)} items")
        
        # Create staging directory for today
        staging_dir = CONFIG["vault_path"] / CONFIG["staging_path"] / source_date
        try:
            staging_dir.mkdir(parents=True, exist_ok=True)
        except (IOError, OSError) as e:
            logger.error(f"Failed to create staging directory {staging_dir}: {e}")
            return False
        
        # Write items
        for item in items:
            try:
                item_path = write_staged_item(
                    item=item,
                    source=source,
                    source_date=source_date,
                    source_file=str(filepath.relative_to(CONFIG["vault_path"])),
                    staging_dir=staging_dir
                )
                logger.info(f"    → {item_path.name}")
            except Exception as e:
                logger.error(f"Failed to write item: {e}")
                continue
        
        # Write summary
        try:
            summary_path = write_extraction_summary(
                extraction=extraction,
                source=source,
                source_date=source_date,
                source_file=str(filepath.relative_to(CONFIG["vault_path"])),
                staging_dir=staging_dir
            )
            logger.info(f"    → {summary_path.name}")
        except Exception as e:
            logger.error(f"Failed to write summary: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to process file {filepath}: {e}")
        return False


def validate_config() -> bool:
    """Validate configuration before running pipeline."""
    vault_path = CONFIG.get("vault_path")
    if not vault_path:
        logger.error("vault_path not configured in CONFIG")
        return False
    
    if not isinstance(vault_path, Path):
        logger.error("vault_path must be a Path object")
        return False
    
    required_keys = ["inbox_paths", "staging_path", "model", "max_tokens"]
    for key in required_keys:
        if key not in CONFIG:
            logger.error(f"Required configuration key missing: {key}")
            return False
    
    return True

def run_pipeline(dry_run: bool = False, single_file: Optional[str] = None) -> None:
    """Run the full pipeline."""
    
    logger.info("=" * 60)
    logger.info("Obsidian Mind Map Pipeline - Phase 1")
    logger.info("=" * 60)
    
    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed")
        return
    
    # Initialize API client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not dry_run:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        logger.error("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        return
    
    # Validate API key format (basic check)
    if api_key and not dry_run:
        if not api_key.startswith("sk-ant-"):
            logger.warning("API key may be invalid - expected format: sk-ant-...")
    
    client = anthropic.Anthropic(api_key=api_key) if api_key else None
    
    # Load processing log
    log = load_processing_log()
    logger.info(f"Last run: {log.get('last_run', 'Never')}")
    
    # Load Bible context
    logger.info("Loading Bible context...")
    bible_context = load_bible_context()
    if bible_context:
        logger.info(f"  Loaded {len(CONFIG['bible_files'])} Bible file(s)")
    else:
        logger.info("  No Bible files loaded (continuing without context)")
    
    # Find files to process
    if single_file:
        filepath = Path(single_file).resolve()
        if not filepath.exists():
            logger.error(f"File not found: {single_file}")
            return
        
        # Validate file is within vault or explicitly allowed
        if not validate_file_path(filepath, CONFIG["vault_path"]):
            logger.error(f"File path is outside vault directory: {single_file}")
            logger.error("For security, only files within the vault can be processed")
            return
        
        # Determine source from path
        source = "unknown"
        for src, inbox_path in CONFIG["inbox_paths"].items():
            if inbox_path in str(filepath):
                source = src
                break
        
        try:
            new_files = [{
                "path": filepath,
                "source": source,
                "hash": get_file_hash(filepath),
            }]
        except Exception as e:
            logger.error(f"Failed to process file {single_file}: {e}")
            return
    else:
        logger.info("Scanning inbox folders...")
        new_files = find_new_files(log)
    
    if not new_files:
        logger.info("  No new files to process")
        return
    
    logger.info(f"  Found {len(new_files)} file(s) to process")
    
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
        try:
            log["last_run"] = datetime.now().isoformat()
            save_processing_log(log)
        except Exception as e:
            logger.error(f"Failed to save processing log: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"Complete! Processed {success_count}/{len(new_files)} files")
    logger.info(f"Staged items in: {CONFIG['vault_path'] / CONFIG['staging_path']}")
    logger.info("=" * 60)


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
