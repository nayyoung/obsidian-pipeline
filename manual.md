# Manual Test Plan - Obsidian Mind Map Pipeline

This document contains manual test cases that cannot be fully automated.
Check off each test as you complete it.

---

## Prerequisites

Before running manual tests:

```bash
# 1. Install dependencies
pip install -r obsidian-pipeline/requirements.txt

# 2. Set up API key
export ANTHROPIC_API_KEY='your-actual-key-here'

# 3. Verify automated tests pass first
python -m pytest tests/ -v


Test Suite 1: Initial Setup
TC-1.1: Fresh Vault Setup
Purpose: Verify setup_vault.py creates correct structure

rm -rf ~/ObsidianVault
python obsidian-pipeline/setup_vault.py

Expected Results:

 All inbox folders created (claude, chatgpt, gemini)
 Processing folders created (01-Processed through 05-Conflicts)
 06-Bibles folder with starter Bible file
 _meta folder created
 .gitignore file created
TC-1.2: Idempotent Setup
python obsidian-pipeline/setup_vault.py

 No errors on second run
 Existing files NOT overwritten
Test Suite 2: CLI Interface
TC-2.1: Help Command
python obsidian-pipeline/pipeline.py --help

 Shows usage with --dry-run and --file options
TC-2.2: Dry Run (No Files)
python obsidian-pipeline/pipeline.py --dry-run

 Shows "No new files to process"
TC-2.3: Missing API Key
unset ANTHROPIC_API_KEY
python obsidian-pipeline/pipeline.py

 Clear error message about missing key
Test Suite 3: Claude Export Processing
TC-3.1: Basic Claude Conversation
Setup: Create file ~/ObsidianVault/00-Inbox/claude/2024-12-07-software-design.txt with a conversation about software design principles.

Run:

export ANTHROPIC_API_KEY='your-key'
python obsidian-pipeline/pipeline.py

Expected Results:

 Processing log shows file being processed
 Staging folder created: 01-Processed/2024-12-07/
 At least one item .md file created (theme/decision/action/insight)
 Summary file _summary-claude-2024-12-07.md created
 All files have valid YAML frontmatter
TC-3.2: Single File Processing
python obsidian-pipeline/pipeline.py --file ~/ObsidianVault/00-Inbox/claude/2024-12-07-software-design.txt

 Only the specified file is processed
 Other files in inbox are NOT processed
TC-3.3: Dry Run with File
python obsidian-pipeline/pipeline.py --dry-run

 Shows what WOULD be processed
 No files actually created
 No API calls made
Test Suite 4: ChatGPT Export Processing
TC-4.1: ChatGPT JSON Export
Setup: Export a conversation from ChatGPT (JSON format) and save to: ~/ObsidianVault/00-Inbox/chatgpt/2024-12-07-chatgpt-export.txt

Run:

python obsidian-pipeline/pipeline.py

Expected Results:

 JSON is parsed correctly
 Messages are normalized (USER:, ASSISTANT: format in API call)
 Output files created in staging folder
 Source shows "chatgpt" in frontmatter
TC-4.2: Invalid JSON Fallback
Setup: Create a file with plain text (not JSON) in chatgpt inbox

 File is processed without error
 Plain text is passed through to API
Test Suite 5: Gemini Export Processing
TC-5.1: Gemini Copy-Paste
Setup: Copy-paste a Gemini conversation to: ~/ObsidianVault/00-Inbox/gemini/2024-12-07-gemini-chat.txt

Run:

python obsidian-pipeline/pipeline.py

 File is processed
 Source shows "gemini" in frontmatter
Test Suite 6: Bible Context Injection
TC-6.1: Bible Context Used
Setup:

Edit ~/ObsidianVault/06-Bibles/Gumroad_Launch_Bible.md with specific project context
Process a conversation file
 Bible content appears in API call (check logs or mock)
 Extracted items may reference Bible concepts
TC-6.2: Missing Bible File
Setup: Delete or rename the Bible file

 Processing continues without error
 Log shows warning about missing Bible file
Test Suite 7: Reprocessing & Change Detection
TC-7.1: Skip Already Processed
Setup: Process a file, then run pipeline again without changes

python obsidian-pipeline/pipeline.py
python obsidian-pipeline/pipeline.py

 Second run shows "No new files to process"
 File is NOT reprocessed
TC-7.2: Detect Modified Files
Setup:

Process a file
Modify the file content
Run pipeline again
 Modified file IS reprocessed
 New output files created
TC-7.3: Processing Log Persistence
 Check _meta/processing_log.json exists
 Contains file paths and hashes
 Contains last_run timestamp
Test Suite 8: Output File Verification
TC-8.1: Frontmatter Structure
Open any generated .md file and verify:

 Starts with ---
 Contains title: field
 Contains type: field (theme/decision/action/insight)
 Contains source: field
 Contains source_date: field
 Contains status: staged
 Contains id: field (12-char hex)
 Ends frontmatter with ---
TC-8.2: Content Structure
 Has main heading with title
 Has content section
 Has "Key Quote" section with blockquote
 Has "Review Notes" section
 Has "Actions" section with checkbox
TC-8.3: Summary File Structure
Open _summary-*.md file:

 Has frontmatter with item_count
 Has "Conversation Summary" section
 Has "Primary Themes" list
 Has "Extracted Items" grouped by type
Test Suite 9: Obsidian Integration
TC-9.1: Open in Obsidian
Open ~/ObsidianVault as a vault in Obsidian
Navigate to 01-Processed/ folder
 Files display correctly
 Frontmatter shows in properties view
 Wiki links [[Theme Name]] are clickable (even if targets don't exist)
TC-9.2: Search Functionality
Use Obsidian search to find:

 Search by title finds items
 Search by key_quote finds items
 Search by type (e.g., type: theme) works
TC-9.3: Graph View
Open Obsidian Graph View:

 Processed items appear as nodes
 Wiki links create connections (if targets exist)
Test Suite 10: Error Handling
TC-10.1: Invalid API Key
export ANTHROPIC_API_KEY='invalid-key'
python obsidian-pipeline/pipeline.py

 Clear error message
 Does not crash
 File not marked as processed (can retry)
TC-10.2: Network Timeout
(Simulate by disconnecting network during processing)

 Retry logic activates (check logs)
 Eventually fails gracefully
 File not marked as processed
TC-10.3: API Rate Limiting
Process many files rapidly:

 Exponential backoff visible in logs
 Eventually succeeds or fails gracefully
TC-10.4: Malformed API Response
(Hard to simulate - skip unless specifically testing)

 JSON decode error is logged
 Processing continues with other files
Test Suite 11: Security Verification
TC-11.1: Path Traversal Prevention
Setup: Try to process a file outside vault:

python obsidian-pipeline/pipeline.py --file /etc/passwd

 Error: "File path is outside vault directory"
 File is NOT read
TC-11.2: Filename Sanitization
Process a conversation that generates items with special characters in titles.

 No files created with path separators (/, )
 No files created starting with dots
 Windows reserved names (CON, PRN, etc.) are prefixed
Test Suite 12: Performance
TC-12.1: Large Conversation
Create a conversation file with 50,000+ characters.

 Processing completes without timeout
 Memory usage reasonable (< 500MB)
 Output files generated correctly
TC-12.2: Batch Processing
Add 10+ files to inbox folders.

python obsidian-pipeline/pipeline.py

 All files processed
 Processing log updated for each
 Reasonable total processing time
Test Completion Summary
Suite	Tests	Passed	Failed
1. Initial Setup	2		
2. CLI Interface	3		
3. Claude Processing	3		
4. ChatGPT Processing	2		
5. Gemini Processing	1		
6. Bible Context	2		
7. Reprocessing	3		
8. Output Verification	3		
9. Obsidian Integration	3		
10. Error Handling	4		
11. Security	2		
12. Performance	2		
TOTAL	30		
Tested By: _________________ Date: _________________
