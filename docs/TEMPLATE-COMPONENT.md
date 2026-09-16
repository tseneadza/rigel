# Component: [Component Name]

## Overview
Brief description of what this component does and where it fits in the application.

## Type
- [ ] React Component
- [ ] Python Module
- [ ] Tauri Native Command
- [ ] Utility/Helper
- [ ] Service

## Location
- **File:** `path/to/component.tsx` or `path/to/module.py`
- **Related Files:** [Other closely-related files]

## Purpose & Responsibilities
What this component is responsible for:
- Responsibility 1
- Responsibility 2
- Responsibility 3

## API / Interface

### Props (React) / Parameters (Python)
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `propName` | `string` | yes | What this prop does |
| `onCallback` | `(data) => void` | no | Callback fired when [event] |

### Return Value / Output
What does this component return or produce?

```typescript
interface ComponentOutput {
  status: 'success' | 'error',
  data?: any,
  error?: string
}
```

### Methods (if applicable)
```python
def method_name(param1: str, param2: int) -> dict:
    """
    What this method does.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        Description of return value
    """
    pass
```

## Dependencies
- **Internal:** [Other components it depends on]
- **External:** [Third-party libraries]

## State Management
- **Local State:** [useState/useState-like variables]
- **Global State:** [Redux/Context/stores used]
- **Props:** [Props that affect rendering]

## Lifecycle / Hooks
- **Mount:** What happens on initialization
- **Updates:** What triggers re-renders
- **Unmount:** Cleanup/teardown logic

## Usage Examples

### React Component
```tsx
<ComponentName 
  propName="value" 
  onCallback={(data) => handleResult(data)}
/>
```

### Python Function
```python
from path.to import component

result = component.method_name(param1="value", param2=123)
```

## Error Handling
- What errors can this component throw?
- How are errors propagated?
- What's the user-facing behavior on error?

## Testing

### Unit Test Example
```python
def test_component_with_valid_input():
    result = component.method_name("valid", 42)
    assert result["status"] == "success"
```

### Test Coverage
- [Test file location]
- Critical paths to test
- Edge cases to cover

## Performance Notes
- Rendering performance (React)
- Computational complexity (Python)
- Memory usage patterns
- Optimization opportunities

## Accessibility (React Components)
- ARIA labels used
- Keyboard navigation support
- Screen reader compatibility
- Color contrast compliance

## Related Components
- [Component A] - How it interacts
- [Component B] - Why they're related

## Future Improvements
- Enhancement 1
- Refactoring opportunity 1

## References
- [Design decisions]
- [Related documentation]
