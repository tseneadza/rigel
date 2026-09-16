# Database Schema: [Table/Collection Name]

## Overview
Purpose of this table/collection and what data it stores.

## Location
- **Database:** SQLite at `~/.rigel/rigel.db`
- **File:** [Which Python file manages this schema]

## Table Definition

### Schema
```sql
CREATE TABLE [table_name] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    [column_name] [TYPE] [CONSTRAINTS],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Columns
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | No | AUTO_INCREMENT | Primary key |
| `column_name` | VARCHAR(255) | No | | What this column stores |
| `foreign_key_id` | INTEGER | No | | Foreign key to [table_name] |
| `data_field` | JSON | Yes | NULL | Flexible data storage |
| `created_at` | TIMESTAMP | No | NOW | Record creation time |

### Indexes
```sql
CREATE INDEX idx_[table]_[column] ON [table_name]([column_name]);
CREATE UNIQUE INDEX idx_[table]_unique ON [table_name]([column_name]);
```

### Foreign Keys
| Column | References | ON DELETE | ON UPDATE |
|--------|-----------|-----------|-----------|
| `user_id` | users.id | CASCADE | CASCADE |

## Relationships
```
[table_name] 1:N [related_table]
[table_name] M:N [another_table] (via [junction_table])
```

## Sample Data
```json
{
  "id": 1,
  "column_name": "value",
  "foreign_key_id": 123,
  "data_field": {"nested": "json"},
  "created_at": "2026-09-13T12:00:00Z"
}
```

## Access Patterns
Common queries that operate on this table:
- **Insert:** When [event happens]
- **Read:** By [criteria], typically [frequency]
- **Update:** When [state changes]
- **Delete:** [Policy for data retention]

## Data Retention Policy
- **Retention Period:** [Duration] or [indefinite]
- **Archival:** [How old data is handled]
- **Deletion:** [Conditions under which records are deleted]

## Performance Considerations
- Expected row count: [estimate]
- Typical query performance: [notes]
- Optimization notes: [Any special considerations]

## Migration History
| Version | Change | Date | Author |
|---------|--------|------|--------|
| 1.0 | Initial schema | 2026-09-13 | [name] |
| 1.1 | Added [column] | 2026-09-14 | [name] |

## Related Code
- **Model:** [Python class file]
- **Queries:** [Functions/methods that access this table]
- **Tests:** [Test files for this schema]

## Notes
- Any caveats or special behaviors
- Known issues or limitations
