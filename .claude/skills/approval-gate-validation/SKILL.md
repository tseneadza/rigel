---
name: approval-gate-validation
description: >
  Required procedure for ANY change to Rigel's approval gates, permission
  checks, or safety mechanisms: adding approval rules, modifying risk levels,
  changing confirmation thresholds, debugging "command approved when it
  shouldn't / permission denied incorrectly / safety bypass" issues. Trigger
  on: approval, permission, gate, safety, risk level, confirmation, "command
  not approved", "wrong permission", "safety issue", "bypass vulnerability".
---

# Approval Gate Validation — the safety triple-check

## Why this skill exists (the silent permission escalation pattern)

Approval gates have multiple failure modes that are security-critical:
- Permission check exists in code but not enforced in gate rules
- Risk level misclassified (dangerous operation marked low-risk)
- Confirmation required but dismissible with default action
- Gate rule written too broadly (allows more than intended)
- Permission check bypassed accidentally (logic error in handler)
- Safety invariant broken (allows conflicting state changes)

A voice command can pass NLP recognition, handler validation, AND gate approval
while still executing something the user didn't authorize. These are invisible
security failures—no error, just wrong action taken on user's behalf.

## The three approval checkpoints

| # | Component | File/Config | What it owns |
|---|-----------|-------------|--------------|
| 1 | Risk assessment | `src/intents/[intent].rs` handler | Operation risk classification, parameter validation, permission checks |
| 2 | Gate rules | `src/approval/gates.toml` + schema | Approval requirements, risk thresholds, confirmation rules |
| 3 | Runtime checks | `src/approval/engine.rs` | Gate decision logic, audit logging, safety enforcement |

**Gate changes touch all three in the same commit.** A risk level change in
gates.toml without corresponding handler logic = silent permission escalation.
A new gate rule without enforcement in the engine = rule ignored.

## Non-negotiable steps for any approval/permission change

1. **Run approval validation tests first and last:**
   ```bash
   cd src/approval && cargo test gate:: -- --include-ignored
   cargo test safety:: -- --include-ignored
   cargo test permission:: -- --include-ignored
   ```
   These enforce: gate rules←→handler parity, risk classification accuracy
   (low/medium/high matches actual danger), all dangerous operations require
   confirmation, permission checks execute before action, gate denial produces
   audit log, no bypass paths, handler can't override gate decision.

2. **Risk classification rules (never skip these):**

   **LOW RISK** (read-only, reversible, no data loss)
   - Opening applications
   - Reading files
   - Querying information
   - Non-destructive queries
   - Example: `open_vs_code`, `get_weather`

   **MEDIUM RISK** (modifies state, reversible, limited scope)
   - Creating files/directories
   - Moving files (user's own directories)
   - Modifying settings
   - Creating calendar events
   - Example: `create_file`, `set_reminder`

   **HIGH RISK** (destructive, irreversible, system-wide impact)
   - Deleting files
   - Modifying system files
   - Changing permissions
   - Executing arbitrary commands
   - Example: `delete_file`, `clear_database`

3. **Define approval changes across all three checkpoints:**

   **Checkpoint 1: Risk classification in handler** (`src/intents/delete_file.rs`)
   ```rust
   pub async fn handle_delete_file(params: DeleteFileParams) -> Result<()> {
     // BEFORE executing ANY action:
     // 1. Validate parameters (path exists, is regular file)
     // 2. Check permissions (user owns file, not system file)
     // 3. Assess risk (classify as HIGH)
     // 4. Request approval from engine (don't decide yourself)
     
     let approval = ApprovalEngine::request_approval(
       IntentName::DeleteFile,
       RiskLevel::High,
       &params,
     ).await?;
     
     if !approval.approved {
       return Err(Error::DeniedByUser(approval.reason));
     }
     
     // NOW execute
     std::fs::remove_file(&params.path)?;
     Ok(())
   }
   ```

   **Checkpoint 2: Gate rules** (`src/approval/gates.toml`)
   ```toml
   [delete_file]
   risk_level = "high"
   requires_confirmation = true
   requires_explanation = true  # Require user to explain why
   confirmation_timeout_ms = 30000
   require_explicit_approval = true  # Can't use default "yes"
   allowed_paths = ["/Users/[username]/Downloads/**"]  # Limit scope
   denied_paths = ["/System/**", "/Users/**/.config/**"]  # Never allow these
   ```

   **Checkpoint 3: Gate enforcement** (`src/approval/engine.rs`)
   ```rust
   pub async fn request_approval(
     intent: IntentName,
     params: &IntentParams,
   ) -> Result<ApprovalDecision> {
     // 1. Look up gate rules
     let gate = self.gates.get(&intent)?;
     
     // 2. Check hard constraints (denied_paths, etc.)
     if self.violates_safety_constraint(intent, params)? {
       return Ok(ApprovalDecision::denied("Safety constraint violated"));
     }
     
     // 3. Request confirmation if required
     if gate.requires_confirmation {
       self.prompt_user_confirmation(intent, params).await?
     } else {
       Ok(ApprovalDecision::approved())
     }
   }
   ```

4. **Safety rules (never violate):**
   - Every dangerous operation (delete, modify, execute) MUST have explicit
     handler check + gate rule
   - Permission checks must run BEFORE gate evaluation (don't ask permission
     for operations user can't do)
   - HIGH risk operations must require explicit user confirmation (can't use defaults)
   - Confirmation can't be skipped, dismissed, or auto-completed
   - All approval decisions must be logged (with intent, params, decision, user)
   - Gate can deny, but handler must also validate (defense in depth)
   - No operation can override gate decision in handler (gate is final authority)

## "Command approved when shouldn't be" debugging

1. **Is the handler checking permissions?**
   ```bash
   grep -n "ApprovalEngine::request" src/intents/[intent].rs
   # Should have gate request BEFORE action
   # If not present: handler bypassing approval
   ```

2. **Is the risk level correct?**
   ```bash
   grep -A 5 "\[delete_file\]" src/approval/gates.toml
   # Should say risk_level = "high"
   # If "low" or "medium": risk misclassified
   ```

3. **Does the gate rule allow this operation?**
   ```bash
   cargo run --bin approval-debug delete_file /path/to/file
   # Should show gate decision and why
   # If approved wrongly: gate rule too permissive
   ```

4. **Are there bypass paths?**
   ```bash
   grep -r "unsafe" src/handlers/
   # Look for unwrap() or force operations
   grep -r "unreachable" src/approval/
   # Check for holes in logic
   ```

## "Permission denied incorrectly" debugging

1. **Is the gate rule too restrictive?**
   ```bash
   cat src/approval/gates.toml | grep -A 10 "\[command_name\]"
   # Check denied_paths, allowed_contexts, etc.
   # Loosen if blocking legitimate operations
   ```

2. **Does the user have actual permission?**
   ```bash
   # Check file ownership, system permissions
   ls -la /path/to/resource
   # User must own or have access rights
   ```

3. **Is the handler validating correctly?**
   ```bash
   cargo run --bin intent-handler-test [intent] -- --debug
   # Should show what permissions were checked
   # If permission check too strict: adjust validation logic
   ```

4. **Did the user actually confirm?**
   ```bash
   # Check approval logs for confirmation record
   cargo run --bin approval-audit -- --limit 10
   # Should show user clicked "approve" button
   ```

## "Safety bypass discovered" response

1. **Assess severity:**
   - Can be exploited by voice alone? (HIGH)
   - Requires physical access? (MEDIUM)
   - Requires code change? (LOW)

2. **Immediate mitigation:**
   ```toml
   # Disable the vulnerable operation immediately
   [dangerous_command]
   risk_level = "critical"
   requires_explanation = true
   allowed_contexts = []  # Disable entirely
   ```

3. **Fix the vulnerability:**
   - Add missing permission check in handler
   - Tighten gate rule constraint
   - Add safety invariant validation
   - Increase risk level if misclassified

4. **Verify the fix:**
   ```bash
   cargo test safety::bypass_tests -- --include-ignored
   # Should fail on bypass attempt
   ```

## Definition of done for approval/permission work

- [ ] Approval validation tests pass: `cargo test gate:: -- --include-ignored`
- [ ] All three checkpoints updated (handler, gate, engine) in same commit
- [ ] Risk level matches actual operation danger
- [ ] Handler checks permissions BEFORE requesting approval
- [ ] HIGH risk operations require explicit user confirmation
- [ ] Gate rule tested with valid and invalid parameters
- [ ] Bypass tests fail (can't bypass gate from handler)
- [ ] Approval audit log complete (intent, params, decision logged)
- [ ] `docs/APPROVAL_GATES.md` updated with new rules
- [ ] Security review passed (no bypass paths)
- [ ] Commit message references all three changed files

---

**Related:** [[intent-definition-integrity]] (intent execution needs approval),
[[desktop-sidecar-communication]] (approval decision crosses IPC boundary),
[[voice-pipeline-integrity]] (voice input requires approval for sensitive commands)
