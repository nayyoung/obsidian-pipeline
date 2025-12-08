#!/usr/bin/env python3
"""
Setup script to initialize Obsidian vault folder structure
for the Mind Map Pipeline.

Run this once to create all necessary folders.
"""

import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Update this to your vault location
VAULT_PATH = Path.home() / "ObsidianVault"

FOLDERS = [
    "00-Inbox/claude",
    "00-Inbox/chatgpt",
    "00-Inbox/gemini",
    "01-Processed",
    "02-Themes",
    "03-Decisions",
    "04-Actions",
    "05-Conflicts",
    "06-Bibles",
    "_meta",
]

def setup_vault():
    logger.info(f"Setting up Obsidian vault at: {VAULT_PATH}")
    logger.info("-" * 50)
    
    for folder in FOLDERS:
        folder_path = VAULT_PATH / folder
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"  ✓ Created: {folder}")
        except (IOError, OSError) as e:
            logger.error(f"  ✗ Failed to create {folder}: {e}")
            continue
    
    # Create starter Bible file
    bible_path = VAULT_PATH / "06-Bibles" / "Gumroad_Launch_Bible.md"
    if not bible_path.exists():
        bible_content = """---
title: Gumroad Launch Bible
type: bible
created: {date}
---

# Gumroad Launch Bible

This is your source of truth for the Gumroad launch project.
Update this document as your plans evolve.

## Current Status
_What phase are you in?_

## Goals
_What are you trying to achieve?_

## Key Decisions Made
_Document important decisions here_

## Open Questions
_What still needs to be figured out?_

## Resources
_Links, references, related notes_
"""
        try:
            bible_path.write_text(bible_content.format(date=datetime.now().strftime("%Y-%m-%d")))
            logger.info(f"  ✓ Created starter Bible: {bible_path.name}")
        except (IOError, OSError) as e:
            logger.error(f"  ✗ Failed to create starter Bible: {e}")
    
    # Create .gitignore if using git
    gitignore_path = VAULT_PATH / ".gitignore"
    if not gitignore_path.exists():
        try:
            gitignore_path.write_text("""# Obsidian
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/plugins/*/data.json

# OS
.DS_Store
Thumbs.db

# Backup files
*.bak
""")
            logger.info(f"  ✓ Created: .gitignore")
        except (IOError, OSError) as e:
            logger.error(f"  ✗ Failed to create .gitignore: {e}")
    
    logger.info("-" * 50)
    logger.info("Setup complete!")
    logger.info("\nNext steps:")
    logger.info(f"1. Open {VAULT_PATH} as a vault in Obsidian")
    logger.info("2. Install recommended plugins: Dataview, Tasks, Templater")
    logger.info("3. Update 06-Bibles/Gumroad_Launch_Bible.md with your actual context")
    logger.info("4. Save conversation exports to 00-Inbox/[source]/ folders")
    logger.info("5. Run: python pipeline.py")


if __name__ == "__main__":
    setup_vault()
