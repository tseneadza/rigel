# Command Intent: [Intent Name]

## Overview
Description of what command intent this represents and what user actions trigger it.

## Intent Identifier
```
rigel:intent:[domain]:[action]
```
Example: `rigel:intent:app:open`

## User Prompts That Trigger This
Common ways users express this intent in natural language:
- "Open VS Code"
- "Launch Chrome"
- "Start the IDE"

## Intent Structure

### Parsed Intent JSON
```json
{
  "intent_type": "app:open",
  "domain": "application",
  "action": "open",
  "target": {
    "type": "application",
    "identifier": "com.microsoft.VSCode",
    "name": "Visual Studio Code"
  },
  "parameters": {
    "parameter1": "value1"
  },
  "confidence": 0.95,
  "raw_user_input": "Open VS Code"
}
```

### Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `intent_type` | string | yes | Categorized intent type |
| `domain` | string | yes | Domain of the action (app, file, system, etc.) |
| `action` | string | yes | Specific action within domain |
| `target` | object | yes | What/who is being acted upon |
| `parameters` | object | no | Additional parameters for the action |
| `confidence` | float | yes | 0-1 confidence score |
| `raw_user_input` | string | yes | Original user prompt |

## Execution

### Required Approvals
Does this intent require explicit user approval before execution?
- [ ] No approval needed
- [x] Requires explicit approval
- [ ] Contextual approval (depends on parameters)

### Execution Handler
```python
# Location: sidecar/brain.py or similar
def execute_app_open(intent: dict) -> dict:
    """
    Execute application open intent.
    
    Returns:
        {
            "status": "success" | "error" | "pending_approval",
            "message": "Human readable result",
            "result": {...}
        }
    """
    pass
```

### Side Effects
What happens when this intent is executed:
- Application is launched
- Files are modified
- System settings change
- Network requests are made

### Rollback/Undo
Can this action be undone? How?

## Validation

### Pre-Execution Checks
- [ ] Parameter validation: [criteria]
- [ ] Permission check: [what permissions are needed]
- [ ] State check: [what system state must exist]
- [ ] Conflict check: [what conflicts to look for]

### Error Handling
| Error Condition | Response | User Feedback |
|-----------------|----------|---------------|
| Target not found | Return error | "I couldn't find VS Code" |
| Permission denied | Ask for approval | "May I open VS Code?" |

## Logging

### What Gets Logged
- User prompt
- Parsed intent structure
- Execution status
- Any errors or warnings
- Execution timestamp

### Storage Location
Data is stored in `~/.rigel/rigel.db` in the `command_intents` table.

## Examples

### Example 1: Simple Application Launch
**User:** "Open VS Code"

```json
{
  "intent_type": "app:open",
  "domain": "application",
  "action": "open",
  "target": {
    "type": "application",
    "identifier": "com.microsoft.VSCode",
    "name": "Visual Studio Code"
  },
  "parameters": {},
  "confidence": 0.98
}
```

### Example 2: File Operation
**User:** "Move project.txt to the Desktop"

```json
{
  "intent_type": "file:move",
  "domain": "filesystem",
  "action": "move",
  "target": {
    "type": "file",
    "path": "/Users/username/project.txt"
  },
  "parameters": {
    "destination": "/Users/username/Desktop"
  },
  "confidence": 0.92
}
```

## Testing

### Test Cases
- [ ] Successfully parse valid user prompt
- [ ] Correctly identify intent type
- [ ] Extract all parameters
- [ ] Handle ambiguous input
- [ ] Reject invalid parameters

### Test Example
```python
def test_parse_app_open_intent():
    prompt = "Open VS Code"
    intent = parse_intent(prompt)
    assert intent["intent_type"] == "app:open"
    assert intent["target"]["name"] == "Visual Studio Code"
    assert intent["confidence"] > 0.9
```

## Related Intents
- [Related intent 1]
- [Related intent 2]

## Future Enhancements
- Support for parameter variations
- Improved intent classification
- Better confidence scoring

## References
- [Brain module documentation]
- [Parser implementation]
