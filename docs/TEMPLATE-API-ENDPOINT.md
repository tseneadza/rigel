# API Endpoint: [Endpoint Name]

## Overview
Brief description of what this endpoint does and its primary use case.

## HTTP Method & Path
```
[GET|POST|PUT|DELETE|PATCH] /api/rigel/[path]
```

## Request

### Headers
```
Content-Type: application/json
[Other required headers]
```

### Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `param_name` | string | yes | What this parameter does |
| `optional_param` | number | no | Default: `value`. Description. |

### Request Body Example
```json
{
  "key": "value",
  "nested": {
    "field": "data"
  }
}
```

## Response

### Success (200/201)
```json
{
  "status": "success",
  "data": {},
  "timestamp": "2026-09-13T12:00:00Z"
}
```

### Error Responses
- **400 Bad Request:** Invalid parameters or missing required fields
- **401 Unauthorized:** Authentication required (if applicable)
- **404 Not Found:** Resource not found
- **500 Internal Server Error:** Unexpected server error

#### Example Error Response
```json
{
  "status": "error",
  "message": "Descriptive error message",
  "code": "ERROR_CODE"
}
```

## Examples

### cURL
```bash
curl -X [GET|POST] http://127.0.0.1:5140/api/rigel/[path] \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'
```

### Python
```python
import requests

response = requests.get(
    'http://127.0.0.1:5140/api/rigel/[path]',
    json={"key": "value"}
)
print(response.json())
```

## Notes
- Any performance considerations
- Concurrency/rate limiting info
- Related endpoints
