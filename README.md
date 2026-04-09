# langmail

A multi-agent Gmail assistant built with LangChain and LangGraph. Reads your inbox, drafts context-aware replies, extracts action items, and flags security risks — all running locally with full user control.

> **Status:** Active development — Phase 1 (Gmail auth + core tools)

---

## Features

- **Smart inbox triage** — categorizes emails by urgency and action required
- **Context-aware drafts** — writes replies that match your tone with that person
- **Task extraction** — pulls deadlines and action items from emails
- **Security scanning** — flags phishing, suspicious links, and social engineering
- **Local-first** — all data stays on your machine, encrypted at rest
- **Never auto-sends** — always creates drafts for your review

---

## Architecture

```
                    User (CLI)
                        |
               [Supervisor Agent]
                /      |       \
               /       |        \
   [Email Reader] [Draft Writer] [Task Extractor]
               \       |        /
                \      |       /
             [Security Assessor]
                        |
               Gmail API (OAuth2)
```

Built on:
- **LangGraph** — agent orchestration and state management
- **LangChain** — tool definitions and LLM integration
- **Claude** (Anthropic) — reasoning and generation
- **Gmail API** — email access via OAuth2

---

## Quickstart

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Anthropic API key
- Google Cloud project with Gmail API enabled

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/langmail.git
cd langmail
uv sync
```

### Setup

```bash
# 1. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# 2. Run Gmail OAuth2 setup wizard
langmail setup
# Follow the browser prompts to authorize Gmail access
```

### Usage

```bash
# Check unread emails
langmail check

# Check urgent/actionable only
langmail check --urgent

# Draft a reply to an email
langmail draft <email-id>

# Show extracted action items
langmail tasks

# Continuous polling mode
langmail watch

# Sync email history (first run)
langmail sync
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `langmail setup` | OAuth2 setup wizard |
| `langmail check` | Check and triage unread emails |
| `langmail check --urgent` | Show urgent/actionable only |
| `langmail draft <id>` | Draft a reply with optional instructions |
| `langmail tasks` | Show all extracted action items |
| `langmail watch` | Continuous polling mode |
| `langmail sync` | Full email history sync |
| `langmail sync --incremental` | Sync recent changes only |
| `langmail privacy show` | Show what data is stored locally |
| `langmail privacy clear-cache` | Delete cached email content |
| `langmail config` | View/edit settings |

---

## Security & Privacy

- **OAuth2** — never stores your Gmail password
- **Encrypted cache** — email bodies cached locally with AES-256 encryption
- **Draft-only** — never sends emails automatically
- **Minimum scopes** — requests only `gmail.readonly` + `gmail.compose`
- **Auto-expiry** — cached email content expires after 7 days by default

See [docs/SECURITY.md](docs/SECURITY.md) for full security model.

---

## Project Structure

```
langmail/
├── src/langmail/
│   ├── cli.py          # Typer CLI app
│   ├── config.py       # Settings management
│   ├── auth.py         # OAuth2 flow + token management
│   ├── state.py        # LangGraph agent state
│   ├── tools/          # LangChain tool definitions
│   ├── agents/         # Sub-agent implementations
│   └── prompts/        # Prompt templates
├── tests/              # pytest test suite
├── docs/               # Architecture and planning docs
└── .github/workflows/  # CI/CD
```

---

## Roadmap

- [x] Project scaffold and planning
- [ ] Gmail OAuth2 authentication
- [ ] SQLite email index + sync
- [ ] Email Reader agent
- [ ] Security Assessor agent
- [ ] Task Extractor agent
- [ ] Draft Writer agent (with context)
- [ ] Supervisor orchestration
- [ ] CLI interface
- [ ] Tests and CI
- [ ] Documentation and demo

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE)
