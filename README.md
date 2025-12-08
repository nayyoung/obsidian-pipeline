[README.md](https://github.com/user-attachments/files/24021455/README.md)
# Obsidian Mind Map Pipeline

Transform AI conversation exports into structured knowledge for your Obsidian vault.

## What This Does

1. **Ingests** conversation exports from Claude, ChatGPT, and Gemini
2. **Analyzes** conversations using Claude API to extract themes, decisions, actions, and insights
3. **Outputs** structured Markdown files with proper frontmatter and wiki links for Obsidian

## Phase 1 Features

- Multi-source ingestion (claude, chatgpt, gemini folders)
- Automatic date parsing from filenames
- Processing log to avoid re-processing files
- Bible file injection for context-aware extraction
- Staged output for manual review

## Quick Start

### 1. Install Dependencies

```bash
cd obsidian-pipeline
pip install -r requirements.txt
```

### 2. Set Your API Key

Get your API key from [console.anthropic.com](https://console.anthropic.com)

```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

Add to your shell profile (~/.zshrc or ~/.bashrc) to persist:
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
```

**Security Note:** 
- Never commit your API key to version control
- Keep your API key private and rotate it if exposed
- The pipeline validates that your key starts with `sk-ant-` for safety
- Use environment variables, never hardcode keys in source files

### 3. Configure Vault Path

Edit `pipeline.py` and `setup_vault.py` to set your vault location:

```python
CONFIG = {
    "vault_path": Path.home() / "ObsidianVault",  # Change this
    ...
}
```

### 4. Initialize Vault Structure

```bash
python setup_vault.py
```

This creates:
```
YourVault/
├── 00-Inbox/
│   ├── claude/      # Drop Claude exports here
│   ├── chatgpt/     # Drop ChatGPT exports here
│   └── gemini/      # Drop Gemini exports here
├── 01-Processed/    # Staged items land here
├── 02-Themes/       # (Phase 2: auto-merged themes)
├── 03-Decisions/    # (Phase 2: reviewed decisions)
├── 04-Actions/      # (Phase 2: action items)
├── 05-Conflicts/    # (Phase 2: detected conflicts)
├── 06-Bibles/       # Your source-of-truth docs
└── _meta/           # Processing logs
```

### 5. Add Your Context

Update `06-Bibles/Gumroad_Launch_Bible.md` with your current project context.
The pipeline reads this to understand your situation when extracting insights.

### 6. Export a Conversation

**Claude:** Select all in conversation, copy, paste into a .txt file

**ChatGPT:** Settings → Data controls → Export data (or copy/paste)

**Gemini:** Copy/paste conversation text

Save to appropriate inbox folder with naming convention:
```
YYYY-MM-DD-topic-name.txt
```

Example: `2024-12-07-brandon-partnership-strategy.txt`

### 7. Run the Pipeline

```bash
# Process all new files
python pipeline.py

# Preview what would be processed (no API calls)
python pipeline.py --dry-run

# Process a specific file
python pipeline.py --file path/to/conversation.txt
```

### 8. Review Staged Items

Open your vault in Obsidian. Check `01-Processed/YYYY-MM-DD/` for:
- Individual item notes (themes, decisions, actions, insights)
- `_summary-*.md` files showing what was extracted

Review each item and drag to appropriate final folder, or delete if not useful.

## File Naming Convention

The pipeline extracts dates from filenames if formatted as:
```
YYYY-MM-DD-description.txt
```

If no date in filename, uses file modification date.

## Customization

### Adding Bible Files

Edit `CONFIG["bible_files"]` in `pipeline.py`:

```python
"bible_files": [
    "06-Bibles/Gumroad_Launch_Bible.md",
    "06-Bibles/Brandon_Partnership_Bible.md",  # Add more
],
```

### Changing the Model

Edit `CONFIG["model"]` in `pipeline.py`:

```python
"model": "claude-sonnet-4-20250514",  # or claude-3-haiku, etc.
```

### Adjusting Extraction Prompt

Edit `prompts/extraction_prompt.py` to tune what gets extracted.

## Recommended Obsidian Plugins

- **Dataview**: Query your extracted knowledge
- **Tasks**: Track action items across vault
- **Templater**: Consistent note creation
- **Calendar**: Timeline view of extractions
- **Obsidian Git**: Version control your vault

## Roadmap (Future Phases)

- [ ] Phase 2: Routing logic (auto-merge themes/actions, stage decisions/insights)
- [ ] Phase 3: Conflict detection with embeddings
- [ ] Phase 4: Upsert with versioning for existing notes
- [ ] Phase 5: Scheduled batch jobs (cron/Task Scheduler)

## Troubleshooting

**"ANTHROPIC_API_KEY not set"**
Make sure you exported the key in your current terminal session.

**"API key may be invalid"**
The pipeline expects keys starting with `sk-ant-`. Verify your key is correct.

**JSON parsing errors**
The API sometimes returns malformed JSON. The pipeline will retry up to 3 times with exponential backoff.

**API rate limit errors**
The pipeline includes automatic retry logic. If you hit rate limits frequently, consider:
- Processing fewer files at once
- Adding delays between batches
- Upgrading your API tier

**Files not being detected**
- Ensure files are `.txt` extension
- Check they're in the correct inbox folder
- Run with `--dry-run` to see what's detected

**Path security errors**
For security, the pipeline only processes files within your vault directory. If you see path validation errors, ensure your file is in the correct location.

**File I/O errors**
Check file permissions and ensure your vault path is correctly configured in `pipeline.py`.

## Cost Estimate

Using Claude Sonnet 4:
- ~$0.003 per 1K input tokens
- ~$0.015 per 1K output tokens

A typical conversation (5-10K tokens) costs ~$0.02-0.05 to process.
Daily processing of 2-3 conversations: ~$3-5/month.
