# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in this project, please report it by:
1. Creating a private security advisory on GitHub
2. Emailing the repository owner directly
3. Do NOT create public issues for security vulnerabilities

## Security Best Practices

### API Key Management

1. **Never commit API keys to version control**
   - Always use environment variables for API keys
   - Add `.env` files to `.gitignore`
   - Rotate keys immediately if accidentally exposed

2. **API Key Validation**
   - The pipeline validates that API keys start with `sk-ant-`
   - Invalid key formats are rejected before API calls

### File Path Security

1. **Path Traversal Protection**
   - All file paths are validated to prevent directory traversal attacks
   - Files must be within the configured vault directory
   - Path sanitization removes dangerous characters from filenames

2. **Input Validation**
   - User input is sanitized before use in file paths
   - Date formats are validated before parsing
   - Configuration is validated on startup

### Cryptographic Hashing

1. **File Integrity**
   - SHA-256 is used for file hashing (not MD5)
   - Hashes are used for change detection, not security purposes

### Error Handling

1. **Secure Error Messages**
   - API errors don't expose sensitive information
   - File paths in errors are relative to vault, not absolute system paths
   - Logging uses appropriate levels (INFO, WARNING, ERROR)

2. **Retry Logic**
   - API calls retry up to 3 times with exponential backoff
   - Network errors are caught and logged appropriately

## Known Limitations

1. **File Content**
   - The pipeline reads and processes file contents
   - Ensure conversation exports don't contain sensitive information you don't want sent to Claude API

2. **Network Communication**
   - All API calls go to Anthropic's servers
   - Conversations are sent over HTTPS
   - Review Anthropic's privacy policy and terms of service

3. **Local File Storage**
   - Processed files are stored locally in your vault
   - Ensure your vault has appropriate file system permissions
   - Consider encrypting your vault if it contains sensitive information

## Dependencies

- `anthropic>=0.39.0` - Official Anthropic Python SDK
  - Regularly updated for security patches
  - Check for updates: `pip install --upgrade anthropic`

## Recommended Security Measures

1. **Vault Protection**
   - Set appropriate file system permissions on your vault directory
   - Consider using encrypted file systems for sensitive vaults
   - Regularly backup your vault with secure backup solutions

2. **Environment Security**
   - Use virtual environments for Python dependencies
   - Keep Python and dependencies updated
   - Review dependency security advisories regularly

3. **Access Control**
   - Limit who has access to your API keys
   - Use separate API keys for different projects
   - Monitor API usage for unusual patterns

## Security Updates

This project follows semantic versioning. Security updates will be clearly marked in release notes.

To update:
```bash
cd obsidian-pipeline
git pull
pip install --upgrade -r requirements.txt
```

## Compliance

- This tool processes data locally and sends it to Anthropic's API
- Review your organization's data handling policies before use
- Ensure compliance with GDPR, CCPA, or other relevant regulations
- Be aware of data residency requirements if applicable
