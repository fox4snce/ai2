# Security and Secrets Management

## API Keys and Credentials

**All API keys and credentials are loaded from environment variables, never hardcoded.**

### Required Environment Variables

- `OPENAI_API_KEY`: OpenAI API key for LLM translation (optional, only needed if using real LLM)

### Usage Pattern

All code uses `os.getenv()` or `os.environ.get()` to load credentials:

```python
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

### Never Commit

- `.env` files (gitignored)
- `*.key`, `*.pem` files (gitignored)
- `secrets.yaml`, `config.local.yaml` (gitignored)
- Any file containing actual API keys or passwords

## Files Ignored by Git

The `.gitignore` file excludes:

- **Database files**: `*.db`, `*.sqlite`, `*.sqlite3`
- **Environment files**: `.env`, `.env.local`, `*.key`, `*.pem`
- **Generated content**: `.toolsmith/`, `mvp/.reports/`, `mvp/.ir/`
- **Build artifacts**: `__pycache__/`, `*.pyc`, `build/`, `dist/`
- **IDE files**: `.idea/`, `.vscode/`, `*.swp`
- **Test outputs**: `*.log`, `coverage.xml`, `htmlcov/`

## Security Best Practices

1. **Never hardcode secrets**: Always use environment variables
2. **Never print secrets**: Even partially (e.g., `api_key[:10]`)
3. **Review before commit**: Check `git status` for any sensitive files
4. **Use `.env` files locally**: Add `.env` to `.gitignore` (already done)
5. **Rotate keys if exposed**: If a key is accidentally committed, rotate it immediately

## Verification

To verify no secrets are in the repository:

```bash
# Check for common secret patterns
grep -r "sk-[a-zA-Z0-9]\{32,\}" . --exclude-dir=.git
grep -r "AKIA[0-9A-Z]\{16\}" . --exclude-dir=.git

# Check for hardcoded API keys
grep -r "api_key\s*=" . --exclude-dir=.git --exclude="*.md"
```

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly rather than opening a public issue.
