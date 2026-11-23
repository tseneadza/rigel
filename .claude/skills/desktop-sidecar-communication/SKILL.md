---
name: desktop-sidecar-communication
description: >
  Required procedure for ANY change to Rigel's desktop↔sidecar IPC protocol,
  message serialization, event routing, or data exchange: modifying message
  formats, changing IPC transport, adding new message types, debugging
  "communication timeout / message dropped / desync" issues. Trigger on:
  sidecar, IPC, message protocol, serialization, event routing, desktop
  communication, "sidecar not responding", "message lost", "commands not
  executing", "data out of sync".
---

# Desktop↔Sidecar Communication — the message contract triple-check

## Why this skill exists (the silent desynchronization pattern)

Split-process architecture creates invisible communication failures:
- Message format defined in desktop but sidecar expects different structure
- New message type added to desktop but sidecar has no handler
- Serialization changes in one process break the other
- Event routing optimized in one direction but not the other
- IPC transport timeout changed without updating error handling
- Data consistency lost when message ordering assumptions break

Desktop and sidecar can ship "independently" and silently fail to communicate.
No crash—just silent timeout, dropped messages, or commands executing in the
wrong order.

## The three communication checkpoints

| # | Component | File/Config | What it owns |
|---|-----------|-------------|--------------|
| 1 | Protocol contract | `src/ipc/protocol.toml` + schema files | Message types, fields, serialization format, versioning |
| 2 | Desktop side | `src/desktop/ipc_client.rs` + handlers | Message sending, deserialization, event handling, timeouts |
| 3 | Sidecar side | `src/sidecar/ipc_server.rs` + handlers | Message receiving, validation, execution, response routing |

**IPC changes touch all three in the same commit.** A new message type in the
protocol without sidecar handler = silent failure. A timeout change in desktop
without corresponding error handling = crashed flow.

## Non-negotiable steps for any IPC/communication change

1. **Run IPC contract tests first and last:**
   ```bash
   cd src/ipc && cargo test protocol:: -- --include-ignored
   cargo test desktop::ipc:: -- --include-ignored
   cargo test sidecar::ipc:: -- --include-ignored
   ```
   These enforce: protocol schema←→desktop parity, protocol schema↔sidecar
   parity, message versioning consistency, serialization round-trip success
   (send→receive→parse = original), event ordering preserved, timeout values
   reasonable (not 0ms, not infinite), error messages match both sides.

2. **Define communication changes across all three points:**

   **Checkpoint 1: Protocol contract** (`src/ipc/protocol.toml`)
   ```toml
   [version]
   major = 1
   minor = 2

   [[messages]]
   type = "execute_intent"
   version = "1.0"
   fields = [
     { name = "intent_id", type = "string", required = true },
     { name = "parameters", type = "json", required = false },
     { name = "approval_token", type = "string", required = true }
   ]
   response = { type = "execution_result", fields = [...] }
   timeout_ms = 5000
   retry_on_timeout = true
   ```

   **Checkpoint 2: Desktop IPC client** (`src/desktop/ipc_client.rs`)
   ```rust
   pub async fn send_execute_intent(
     &self,
     intent_id: &str,
     params: Option<JsonValue>,
     token: &str
   ) -> Result<ExecutionResult> {
     // Serialize to protocol format
     // Send with timeout tracking
     // Wait for response matching schema
     // Handle timeout/error per protocol
   }
   ```

   **Checkpoint 3: Sidecar IPC server** (`src/sidecar/ipc_server.rs`)
   ```rust
   async fn handle_execute_intent(&self, msg: ExecuteIntentMessage) -> Result<()> {
     // Validate message against schema
     // Validate token/permissions
     // Execute handler
     // Send response matching protocol
   }
   ```

3. **Message contract rules (never violate these):**
   - Protocol version increments on ANY format change (schema, fields, types)
   - Each message must define required fields (no "sometimes present")
   - Response message must mirror request message structure
   - Timeout values must be ≥ network latency + handler processing time
   - Error responses must include error code + human message
   - Never add optional fields without version bump
   - New message types must be added to protocol FIRST (before handlers)

4. **Event ordering & consistency:**
   - Commands must execute in received order (no race conditions)
   - Responses must correlate to requests (include request_id)
   - State changes must be atomic (all-or-nothing, no partial updates)
   - Acknowledgments must precede state changes (no "fire and forget" on state)

## "Sidecar not responding" debugging order (before touching code)

1. **Is the sidecar process running?**
   ```bash
   ps aux | grep sidecar
   # If not running: start it
   cargo run --bin rigel-sidecar
   ```

2. **Can desktop reach sidecar?**
   ```bash
   cargo run --bin ipc-connectivity-test
   # Should show successful connection
   # If fails: IPC transport (socket/pipe) issue
   ```

3. **Is protocol version mismatch?**
   ```bash
   cargo run --bin protocol-version-check
   # Desktop and sidecar should report same protocol version
   # If different: one process is outdated
   ```

4. **Does sidecar accept the message format?**
   ```bash
   cargo run --bin sidecar-message-test execute_intent
   # Should receive and acknowledge message
   # If fails: message schema mismatch
   ```

5. **Is handler executing?**
   ```bash
   cargo run --bin sidecar-debug -- --log-level=debug
   # Watch logs for message receipt and handler execution
   # If message received but handler silent: logic error
   ```

6. **Test full round-trip (send → receive → respond):**
   ```bash
   cargo test ipc::e2e_roundtrip -- --include-ignored
   # Simulates desktop→sidecar→response→desktop
   # Should complete within timeout
   ```

## "Message dropped" debugging order

1. **Check network conditions (for remote sidecar only):**
   ```bash
   ping -c 5 [sidecar_host]
   # High latency? Packet loss? Firewall blocking?
   ```

2. **Check IPC buffer/queue status:**
   ```bash
   cargo run --bin ipc-queue-status
   # Shows queue depth, dropped count, capacity
   # If full: queue overflow dropping messages
   ```

3. **Check timeout values:**
   ```bash
   grep -n "timeout" src/ipc/protocol.toml
   # Is timeout too short for handler? Increase if reasonable
   # Is timeout infinite? Risk of hanging
   ```

4. **Check error handling:**
   ```bash
   cargo run --bin desktop-ipc-client -- --debug
   # Should show send success/failure per message
   # Trace what happens on timeout
   ```

## "Commands executing out of order" debugging

1. **Check message ordering in protocol:**
   ```bash
   cargo run --bin message-order-test
   # Should execute in received order
   # If out of order: concurrency issue in sidecar
   ```

2. **Check for race conditions:**
   - Are handlers running in parallel? (check sidecar thread pool)
   - Are state updates protected? (check mutex/atomic usage)
   - Do responses include request_id for correlation?

3. **Enable request ID tracking:**
   ```bash
   cargo run --bin rigel-sidecar -- --trace-requests
   # Will log every message with correlation ID
   ```

## Definition of done for IPC/communication work

- [ ] IPC contract tests pass: `cargo test protocol:: -- --include-ignored`
- [ ] Desktop and sidecar IPC tests pass together
- [ ] All three checkpoints updated in same commit
- [ ] Protocol version bumped if ANY format changed
- [ ] Message schemas validate: `cargo test ipc::schema_validation`
- [ ] Serialization round-trip passes: send → receive → parse == original
- [ ] Error handling covers all failure modes (timeout, invalid format, handler error)
- [ ] Timeout values reasonable for expected handler latency
- [ ] Full IPC round-trip test passes: `cargo test ipc::e2e_roundtrip`
- [ ] `docs/IPC_PROTOCOL.md` updated with new message types
- [ ] Commit message references all three changed files/sections

---

**Related:** [[voice-pipeline-integrity]] (audio data crosses IPC boundary),
[[intent-definition-integrity]] (intent execution commands cross IPC), [[database-schema-integrity]] (state changes must sync across processes)
