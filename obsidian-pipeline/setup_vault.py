#!/usr/bin/env python3
"""
Setup script to initialize Obsidian vault folder structure
for the Mind Map Pipeline.

Run this once to create all necessary folders.
"""

from pathlib import Path

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
    print(f"Setting up Obsidian vault at: {VAULT_PATH}")
    print("-" * 50)
    
    for folder in FOLDERS:
        folder_path = VAULT_PATH / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created: {folder}")
    
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
        from datetime import datetime
        bible_path.write_text(bible_content.format(date=datetime.now().strftime("%Y-%m-%d")))
        print(f"  ✓ Created starter Bible: {bible_path.name}")
    
    # Create .gitignore if using git
    gitignore_path = VAULT_PATH / ".gitignore"
    if not gitignore_path.exists():
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
        print(f"  ✓ Created: .gitignore")
    
    print("-" * 50)
    print("Setup complete!")
    print(f"\nNext steps:")
    print(f"1. Open {VAULT_PATH} as a vault in Obsidian")
    print(f"2. Install recommended plugins: Dataview, Tasks, Templater")
    print(f"3. Update 06-Bibles/Gumroad_Launch_Bible.md with your actual context")
    print(f"4. Save conversation exports to 00-Inbox/[source]/ folders")
    print(f"5. Run: python pipeline.py")


if __name__ == "__main__":
    setup_vault()
