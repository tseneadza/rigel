# Documentation Quick Reference

Need to create documentation? Use this quick guide to pick the right template.

## Decision Tree

### What are you documenting?

**An HTTP API endpoint?**
→ Use [`TEMPLATE-API-ENDPOINT.md`](TEMPLATE-API-ENDPOINT.md)
- Sidecar API routes
- New `/api/rigel/*` endpoints
- REST endpoints
- WebSocket endpoints

**A user-facing feature?**
→ Use [`TEMPLATE-FEATURE.md`](TEMPLATE-FEATURE.md)
- Voice input system
- Command execution
- Message persistence
- New UI functionality
- User workflows

**Code (React component, Python module, etc.)?**
→ Use [`TEMPLATE-COMPONENT.md`](TEMPLATE-COMPONENT.md)
- React: RigelOrb, ChatConsole, etc.
- Python: brain.py, db.py, services
- Utility functions/helpers
- Utility classes

**System architecture or design?**
→ Use [`TEMPLATE-ARCHITECTURE.md`](TEMPLATE-ARCHITECTURE.md)
- How desktop talks to sidecar
- Communication patterns
- Data flow between components
- System design decisions
- Major refactoring or redesign

**Database table or data model?**
→ Use [`TEMPLATE-DATABASE-SCHEMA.md`](TEMPLATE-DATABASE-SCHEMA.md)
- New SQLite tables
- Data model changes
- Schema relationships
- Migration history
- Query patterns

**A user intent (voice command)?**
→ Use [`TEMPLATE-COMMAND-INTENT.md`](TEMPLATE-COMMAND-INTENT.md)
- New intent types (app:open, file:move, etc.)
- Command parsing
- Execution logic
- Natural language variations

**Setup or installation instructions?**
→ Use [`TEMPLATE-SETUP-GUIDE.md`](TEMPLATE-SETUP-GUIDE.md)
- Environment setup
- Development environment
- Feature-specific setup
- Configuration steps
- Initial prerequisites

**Debugging or troubleshooting?**
→ Use [`TEMPLATE-TROUBLESHOOTING.md`](TEMPLATE-TROUBLESHOOTING.md)
- Common errors and fixes
- Diagnostic procedures
- Known issues
- Performance debugging
- Development issues

---

## One-Minute Templates

### Fastest Copy-Paste

Need just the structure? Here are minimal versions:

#### API Endpoint (bare minimum)
```markdown
# API: [Name]

**Endpoint:** `[METHOD] /api/rigel/path`

**Request:**
```json
{}
```

**Response:**
```json
{ "status": "success" }
```

**Examples:** [cURL example]
```

#### Feature (bare minimum)
```markdown
# Feature: [Name]

**What it does:** [One sentence]

**How it works:**
1. [Step 1]
2. [Step 2]

**Status:** [Planned/Development/Production]

**Usage:** [Code example]
```

#### Component (bare minimum)
```markdown
# Component: [Name]

**Location:** `path/to/component.tsx`

**Purpose:** [What it does]

**Props:**
| Name | Type | Description |
|------|------|-------------|
| prop | type | description |

**Usage:**
\`\`\`tsx
<Component prop="value" />
\`\`\`
```

---

## Quick Checklist

### Before Writing Docs, Ask Yourself:

- [ ] Is this a new API endpoint? → API-ENDPOINT template
- [ ] Is this a new user-facing feature? → FEATURE template
- [ ] Is this a reusable code module? → COMPONENT template
- [ ] Is this about how things work together? → ARCHITECTURE template
- [ ] Is this about data storage? → DATABASE-SCHEMA template
- [ ] Is this something users can command Rigel to do? → COMMAND-INTENT template
- [ ] Is this about setting up/installing? → SETUP-GUIDE template
- [ ] Is this about fixing problems? → TROUBLESHOOTING template
- [ ] None of the above? → Create a custom `.md` file

---

## File Naming Conventions

When you create documentation from templates:

```
docs/
├── api/
│   └── [endpoint-name].md          # Example: chat-endpoint.md
├── features/
│   └── [feature-name].md           # Example: voice-input.md
├── components/
│   └── [component-name].md         # Example: RigelOrb.md
├── architecture/
│   └── [system-name].md            # Example: desktop-sidecar-communication.md
├── database/
│   └── [table-name].md             # Example: conversation-log.md
├── intents/
│   └── [intent-type].md            # Example: app-open.md
├── setup/
│   └── [guide-name].md             # Example: development-environment.md
└── troubleshooting/
    └── [issue-category].md         # Example: sidecar-errors.md
```

---

## Template Selection Matrix

| Need | Template | Why |
|------|----------|-----|
| "How do I call this endpoint?" | `TEMPLATE-API-ENDPOINT.md` | Clear request/response structure |
| "How does this feature work?" | `TEMPLATE-FEATURE.md` | User perspective + implementation |
| "What does this code do?" | `TEMPLATE-COMPONENT.md` | API + usage for developers |
| "How do systems interact?" | `TEMPLATE-ARCHITECTURE.md` | Diagrams + data flow |
| "What's in this table?" | `TEMPLATE-DATABASE-SCHEMA.md` | Schema + access patterns |
| "What can users ask Rigel to do?" | `TEMPLATE-COMMAND-INTENT.md` | Intent structure + examples |
| "How do I set this up?" | `TEMPLATE-SETUP-GUIDE.md` | Step-by-step + verification |
| "Why isn't it working?" | `TEMPLATE-TROUBLESHOOTING.md` | Issues + diagnosis + fixes |

---

## Copy-Paste Commands

### Create a new API documentation file
```bash
cp docs/TEMPLATE-API-ENDPOINT.md docs/api/[endpoint-name].md
# Edit docs/api/[endpoint-name].md
```

### Create a new feature documentation file
```bash
cp docs/TEMPLATE-FEATURE.md docs/features/[feature-name].md
# Edit docs/features/[feature-name].md
```

### Create a new component documentation file
```bash
cp docs/TEMPLATE-COMPONENT.md docs/components/[component-name].md
# Edit docs/components/[component-name].md
```

### Create a new troubleshooting guide
```bash
cp docs/TEMPLATE-TROUBLESHOOTING.md docs/troubleshooting/[issue-name].md
# Edit docs/troubleshooting/[issue-name].md
```

---

## Tips & Tricks

### Save Time
- Copy the whole template, not just sections
- Keep template section headers (they provide structure)
- Use `[Bracketed]` placeholders, replace with Find & Replace

### Make Great Docs
- Start with an example, fill in details from the example
- Keep sections you use, delete sections you don't
- Link between docs: `[See Feature Doc](../features/feature-name.md)`
- Update docs when code changes; don't let them rot

### Stay Organized
- One doc per concept (one API per file, one component per file)
- Use directories (`api/`, `features/`, etc.) to organize
- Index important docs in directory-level `README.md`
- Link related docs together

---

## Still Stuck?

1. **Pick the closest match** from the templates
2. **Read the full template** (templates are examples too)
3. **Look at existing docs** in the project for style
4. **When in doubt**, use `TEMPLATE-FEATURE.md` (most flexible)

---

## See Also

- Full templates: [README.md](README.md)
- Main Rigel README: [../../README.md](../../README.md)
