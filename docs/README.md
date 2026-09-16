# Rigel Documentation

Welcome to the Rigel documentation. This directory contains templates and guides to help you understand, develop, and contribute to the project.

## Documented Features

Real, filled-in documentation (as opposed to the `TEMPLATE-*.md` files
below) lives in `api/`, `architecture/`, `features/`, `setup/`, and
`troubleshooting/`. First example — the LLM brain:
- [Setup](setup/llm-brain.md) · [Feature](features/llm-brain.md) ·
  [Architecture](architecture/llm-provider-selection.md) ·
  [API](api/llm-settings-endpoints.md) ·
  [Troubleshooting](troubleshooting/llm-brain.md)

## Quick Navigation

### For New Contributors
1. **Start here:** [Setup Guide](TEMPLATE-SETUP-GUIDE.md) - Get Rigel running on your machine
2. **Then read:** [Architecture Overview](TEMPLATE-ARCHITECTURE.md) - Understand how components work together
3. **Explore:** [Component Documentation](TEMPLATE-COMPONENT.md) - Learn about specific modules
4. **Get stuck?** [Troubleshooting Guide](TEMPLATE-TROUBLESHOOTING.md) - Debug common issues

### For Developers Working on Features
1. [Feature Documentation](TEMPLATE-FEATURE.md) - How to document new features
2. [API Endpoint Documentation](TEMPLATE-API-ENDPOINT.md) - Document new endpoints
3. [Component Documentation](TEMPLATE-COMPONENT.md) - Document React/Python components
4. [Command Intent Documentation](TEMPLATE-COMMAND-INTENT.md) - Add new user intents

### For Maintainers
1. [Architecture Guide](TEMPLATE-ARCHITECTURE.md) - Design decisions and system design
2. [Database Schema Documentation](TEMPLATE-DATABASE-SCHEMA.md) - Manage data model
3. [Command Intent Documentation](TEMPLATE-COMMAND-INTENT.md) - Intent parsing system
4. [Troubleshooting Guide](TEMPLATE-TROUBLESHOOTING.md) - Support users

---

## Documentation Templates

Each template is designed to be copied and customized for your specific needs. Use them as a starting point—remove sections that don't apply, add more details as needed.

### Core Templates

#### [TEMPLATE-API-ENDPOINT.md](TEMPLATE-API-ENDPOINT.md)
Use this when documenting HTTP endpoints in the sidecar API.
- **When to use:** Adding a new `/api/rigel/*` endpoint
- **Location:** Copy to `docs/api/[endpoint-name].md`
- **Key sections:** Request/response structure, examples, error cases

#### [TEMPLATE-FEATURE.md](TEMPLATE-FEATURE.md)
Use this to document user-facing features end-to-end.
- **When to use:** Launching a new feature (voice input, command execution, etc.)
- **Location:** Copy to `docs/features/[feature-name].md`
- **Key sections:** Overview, technical implementation, usage, testing

#### [TEMPLATE-COMPONENT.md](TEMPLATE-COMPONENT.md)
Use this for React components, Python modules, or utility functions.
- **When to use:** Documenting a module others will depend on
- **Location:** Copy to `docs/components/[component-name].md`
- **Key sections:** API, dependencies, lifecycle, testing

#### [TEMPLATE-ARCHITECTURE.md](TEMPLATE-ARCHITECTURE.md)
Use this to explain system design and architectural patterns.
- **When to use:** Explaining how major systems work or interact
- **Location:** Copy to `docs/architecture/[system-name].md`
- **Key sections:** Components, data flow, design tradeoffs

#### [TEMPLATE-DATABASE-SCHEMA.md](TEMPLATE-DATABASE-SCHEMA.md)
Use this to document database tables and data models.
- **When to use:** Adding a new table or modifying schema
- **Location:** Copy to `docs/database/[table-name].md`
- **Key sections:** Schema, relationships, access patterns, retention

#### [TEMPLATE-COMMAND-INTENT.md](TEMPLATE-COMMAND-INTENT.md)
Use this to document new command intents that users can trigger.
- **When to use:** Adding a new intent type (app:open, file:move, etc.)
- **Location:** Copy to `docs/intents/[intent-name].md`
- **Key sections:** Intent structure, execution, examples, testing

#### [TEMPLATE-SETUP-GUIDE.md](TEMPLATE-SETUP-GUIDE.md)
Use this for installation and configuration instructions.
- **When to use:** Documenting new setup steps or feature configuration
- **Location:** Copy to `docs/setup/[guide-name].md` or update existing setup
- **Key sections:** Prerequisites, step-by-step, verification, troubleshooting

#### [TEMPLATE-TROUBLESHOOTING.md](TEMPLATE-TROUBLESHOOTING.md)
Use this to collect debugging information and solutions.
- **When to use:** Documenting known issues and their fixes
- **Location:** Copy to `docs/troubleshooting/[component-name].md`
- **Key sections:** Common issues, diagnosis, solutions, debugging

---

## How to Use These Templates

### Step 1: Choose the Right Template
Look at your task and match it to a template:
- Adding a database table? → `TEMPLATE-DATABASE-SCHEMA.md`
- Creating a React component? → `TEMPLATE-COMPONENT.md`
- Adding an API endpoint? → `TEMPLATE-API-ENDPOINT.md`
- Launching a new feature? → `TEMPLATE-FEATURE.md`

### Step 2: Copy the Template
```bash
# Example: documenting the chat endpoint
cp docs/TEMPLATE-API-ENDPOINT.md docs/api/chat-endpoint.md
```

### Step 3: Customize
Replace all `[Bracketed]` sections with your actual content:
- Remove sections that don't apply to your feature
- Add links between related docs using markdown `[text](path)`
- Keep examples concrete and complete

### Step 4: Link from Index
Update a relevant index or README to link to your new doc:
- New API endpoint? Add to `docs/api/README.md` or similar
- New feature? Add to `docs/features/README.md`

---

## Organization

Consider organizing your documentation like this:

```
docs/
├── README.md                           ← You are here
├── TEMPLATE-*.md                       ← Template files
├── api/
│   ├── README.md
│   ├── chat-endpoint.md
│   └── health-endpoint.md
├── features/
│   ├── voice-input.md
│   ├── command-execution.md
│   └── conversation-memory.md
├── components/
│   ├── RigelOrb.md
│   ├── ChatConsole.md
│   └── brain.md
├── architecture/
│   ├── overview.md
│   └── desktop-to-sidecar.md
├── database/
│   ├── conversation-log.md
│   └── command-intents.md
├── intents/
│   ├── app-open.md
│   └── file-move.md
├── setup/
│   ├── development.md
│   └── production-deployment.md
└── troubleshooting/
    ├── common-issues.md
    └── debugging-guide.md
```

---

## Best Practices

### Writing
- **Be specific:** Use actual examples and code
- **Be concise:** Remove content that doesn't add value
- **Be current:** Update docs when code changes
- **Link related docs:** Help readers navigate between related topics

### Maintenance
- **One concept per file:** Don't mix features/architecture/API in one doc
- **Use frontmatter** for metadata (if needed):
  ```markdown
  ---
  title: API Endpoint Documentation
  status: stable
  last_updated: 2026-09-13
  ---
  ```
- **Version specific sections:** Mark deprecated features clearly
- **Add timestamps** to examples so readers know they're current

### Examples
- **Show real usage:** Copy/paste from actual code if possible
- **Include errors:** Show what happens when things go wrong
- **Update with code:** If you change code, update examples
- **Test your examples:** Run them yourself before merging

---

## Template Reference

| Template | Use For | Key Content |
|----------|---------|-------------|
| `TEMPLATE-API-ENDPOINT.md` | HTTP endpoints | Request/response, errors, examples |
| `TEMPLATE-FEATURE.md` | User features | Overview, architecture, usage, testing |
| `TEMPLATE-COMPONENT.md` | Code modules | API, dependencies, lifecycle, testing |
| `TEMPLATE-ARCHITECTURE.md` | System design | Components, data flow, tradeoffs |
| `TEMPLATE-DATABASE-SCHEMA.md` | Data models | Schema, relationships, access patterns |
| `TEMPLATE-COMMAND-INTENT.md` | User intents | Intent structure, execution, examples |
| `TEMPLATE-SETUP-GUIDE.md` | Installation | Prerequisites, steps, verification |
| `TEMPLATE-TROUBLESHOOTING.md` | Debugging | Issues, diagnosis, solutions |

---

## Contributing Documentation

Have an improvement to a template? Found a missing section? Open a pull request!

When contributing:
1. Update templates in this directory
2. Add examples from real Rigel code when possible
3. Test setup guides by following them yourself
4. Keep templates generic (they should work for similar features/components)

---

## Links to Main Project

- **Main README:** [../../README.md](../../README.md)
- **Contributing:** [../../CONTRIBUTING.md](../../CONTRIBUTING.md) (if it exists)
- **GitHub:** [github.com/tseneadza/rigel](https://github.com/tseneadza/rigel)

---

## Questions?

If you can't find what you're looking for:
1. Check the [Troubleshooting Guide](TEMPLATE-TROUBLESHOOTING.md)
2. Search existing documentation
3. Open an issue on GitHub
4. Ask in the project discussions

Happy documenting! 🌌
