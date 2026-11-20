---
name: intent-definition-integrity
description: >
  Required procedure for ANY new user intent (voice command) in Rigel: defining
  natural language patterns, creating intent JSON structure, implementing
  execution handlers, adding approval gates, or debugging "intent not
  recognized / wrong command executed / intent ambiguous" issues. Trigger on:
  intent, voice command, command execution, user expression, NLP, natural
  language parsing, approval gate, "voice command not working", "wrong intent
  triggered", "command ambiguous".
---

# Intent Definition Integrity — the four-layer intent stack

## Why this skill exists (the silent misinterpretation pattern)

Voice intents have a four-layer contract that can fail invisibly:
- **Layer 1 (NLP):** Natural language patterns defined but not recognized
- **Layer 2 (JSON):** Intent structure defined but parser can't deserialize
- **Layer 3 (Handler):** Execution logic exists but approval gate blocks it
- **Layer 4 (Approval):** Gate approves but actual action permission missing

An intent can pass NLP tests, exist in JSON, have working handlers, and still
execute wrong commands because the approval gate wasn't updated. No error is
thrown—the command just silently falls through to a default behavior.

## The four-layer intent stack

| Layer | File/Config | What it owns | Failure mode |
|-------|-------------|--------------|--------------|
| 1 | `src/intents/patterns.toml` | Natural language patterns, utterance variations, synonyms | NLP doesn't match user speech |
| 2 | `src/intents/schemas.json` | Intent JSON structure, parameter types, defaults | Parser fails silently, action doesn't execute |
| 3 | `src/handlers/[intent_name].rs` | Execution logic, parameter validation, action dispatch | Handler executes wrong thing, permission check missing |
| 4 | `src/approval/gates.toml` | Approval rules per intent, user confirmation thresholds, safety checks | Gate approves dangerous command, or blocks safe one |

**A new intent must be defined in all four layers in the same commit.** An
intent in 1+2+3 but not 4 gets blocked. An intent in all four but with wrong
parameters gets approved anyway.

## Non-negotiable steps for any intent definition

1. **Run intent validation tests first and last:**
   ```bash
   cd src/intents && cargo test intent:: -- --include-ignored
   cargo test handler:: -- --include-ignored
   cargo test approval:: -- --include-ignored
   ```
   These enforce: pattern↔schema parity (both directions), schema↔handler
   match, handler→approval gate connectivity, all required parameters present,
   no undefined actions in gate rules, semantic accuracy (intent name matches
   actual action), approval thresholds reasonable (not always approve/deny).

2. **Define the intent across all four layers:**

   **Layer 1: NLP patterns** (`src/intents/patterns.toml`)
   ```toml
   [open_vs_code]
   patterns = [
     "open vs code",
     "launch visual studio code",
     "start vscode",
     "open code editor"
   ]
   synonyms = { editor: ["code", "vs code", "vscode"] }
   ```

   **Layer 2: Intent schema** (`src/intents/schemas.json`)
   ```json
   {
     "name": "open_vs_code",
     "description": "Open Visual Studio Code",
     "parameters": {
       "path": { "type": "string", "default": null },
       "workspace": { "type": "string", "default": null }
     },
     "required_params": []
   }
   ```

   **Layer 3: Execution handler** (`src/handlers/open_vs_code.rs`)
   ```rust
   pub fn handle_open_vs_code(params: OpenVSCodeParams) -> Result<()> {
     // Validate params
     // Check permissions: user allowed to launch apps?
     // Execute: open app with optional path
     // Return success/failure
   }
   ```

   **Layer 4: Approval gate** (`src/approval/gates.toml`)
   ```toml
   [open_vs_code]
   requires_confirmation = false
   risk_level = "low"
   allowed_contexts = ["desktop", "voice"]
   ```

3. **Semantic validation rules:**
   - Intent name must describe the action (e.g., `open_vs_code`, not `action_5`)
   - Patterns must NOT overlap with existing intents (test for conflicts)
   - Parameters must match schema exactly (no extra/missing fields)
   - Handler must validate all input parameters before executing
   - Approval gate thresholds must match actual risk (low/medium/high)
   - Dangerous operations (delete, modify, system changes) need confirmation

4. **Handler implementation requirements:**
   - Validate all parameters (type check, range check, path validation)
   - Check user permissions before executing (don't rely on gate alone)
   - Log execution with timestamp and parameters
   - Return clear success/error messages for user feedback
   - Never fall through to default behavior on error
   - Test with and without approval confirmation

## "Intent not recognized" debugging order (before touching code)

1. **Is the pattern defined?**
   ```bash
   grep -r "open vs code" src/intents/patterns.toml
   # If not found: add to patterns.toml
   ```

2. **Does the pattern match NLP test?**
   ```bash
   cargo run --bin intent-nlp-test -- "open vs code"
   # Should print matched intent: open_vs_code
   # If no match: pattern not matching user speech
   ```

3. **Is the schema valid?**
   ```bash
   cargo test intent::schema_validation -- --nocapture
   # Should pass validation
   # If fails: schema JSON is malformed
   ```

4. **Does the handler exist and respond?**
   ```bash
   cargo run --bin intent-handler-test open_vs_code
   # Should execute without error
   # If error: handler missing or broken
   ```

5. **Does the approval gate allow execution?**
   ```bash
   cargo run --bin approval-gate-test open_vs_code
   # Should approve/request confirmation as configured
   # If blocked: gate rule preventing execution
   ```

6. **Test end-to-end (all four layers):**
   ```bash
   cargo test intent::e2e_open_vs_code -- --include-ignored
   # Simulates full flow: speech → NLP → handler → approval → execution
   ```

## "Wrong intent triggered" debugging order

1. **Is the pattern too broad?**
   ```bash
   cargo run --bin intent-pattern-conflicts
   # Lists patterns that could match multiple intents
   # If conflicts: make patterns more specific
   ```

2. **Does schema match what handler expects?**
   ```bash
   diff <(cargo run --bin schema-dump open_vs_code) \
        <(cargo run --bin handler-params open_vs_code)
   # Parameters should match exactly
   ```

3. **Is handler executing wrong action?**
   ```bash
   cargo run --bin intent-handler-test open_vs_code -- --debug
   # Should show what command actually executed
   # Trace through handler logic for logic errors
   ```

4. **Is approval gate passing wrong intent?**
   ```bash
   cargo run --bin approval-gate-debug open_vs_code
   # Should show gate decision and why
   ```

## Definition of done for new intent

- [ ] Intent validation tests pass: `cargo test intent:: -- --include-ignored`
- [ ] All four layers defined (patterns, schema, handler, gate) in same commit
- [ ] Pattern doesn't conflict with existing intents
- [ ] Schema validates: `cargo test intent::schema_validation`
- [ ] Handler tested with valid and invalid parameters
- [ ] Approval gate threshold matches actual risk level
- [ ] Handler checks permissions before executing
- [ ] End-to-end test passes: `cargo test intent::e2e_[intent_name]`
- [ ] User expressions/patterns documented in `docs/intents.md`
- [ ] Commit message references all four changed files/sections

---

**Related:** [[voice-pipeline-integrity]] (clean audio enables accurate intent
recognition), [[desktop-sidecar-communication]] (intent execution crosses IPC
boundary)
