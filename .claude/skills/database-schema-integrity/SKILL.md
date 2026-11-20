---
name: database-schema-integrity
description: >
  Required procedure for ANY database schema change in Rigel: adding columns,
  modifying tables, creating migrations, updating ORM models, or debugging
  "migration failed / data loss / query errors" issues. Trigger on: database,
  schema, migration, ORM model, table, column, "database error", "migration
  failed", "query broken", "data lost", "schema mismatch".
---

# Database Schema Integrity — the migration triple-sync

## Why this skill exists (the silent schema divergence pattern)

Database schemas have three sources of truth that can silently diverge:
- **Schema definition:** SQL migration files define the current state
- **ORM models:** Code models expected by application
- **Database state:** What's actually in the running database

A column can be added to the schema but not reflected in the ORM model. An ORM
field can be removed but the database column left behind (orphaned data). A
migration can work in development but fail in production with an existing
database. No error is thrown until runtime query fails or data is corrupted.

## The three schema checkpoints

| # | Source | File/Config | What it owns |
|---|--------|-------------|--------------|
| 1 | Migrations | `db/migrations/` | SQL schema definition, version history, data transformations |
| 2 | ORM models | `src/models/` | Rust/application data models, validation rules, relationships |
| 3 | Runtime DB | Production database state | Actual tables, columns, constraints, data |

**Schema changes touch all three in the same series of commits.** A migration
without ORM model = runtime query errors. An ORM model without migration =
database column doesn't exist.

## Non-negotiable steps for any database schema change

1. **Run schema validation tests first and last:**
   ```bash
   cd db && sqlx prepare --database-url $DATABASE_URL
   cargo test db::schema:: -- --include-ignored
   cargo test models::validation:: -- --include-ignored
   ```
   These enforce: migration←→ORM model parity (both directions), all ORM
   fields have backing columns, no orphaned columns, no missing indexes on
   foreign keys, constraint consistency (unique/not-null matches ORM), no data
   loss in migrations, rollback always works.

2. **Create schema changes in strict order:**

   **Step 1: Write migration** (`db/migrations/[timestamp]_change_description.sql`)
   ```sql
   -- UP (apply)
   ALTER TABLE intents ADD COLUMN last_executed_at TIMESTAMP NULL;
   CREATE INDEX idx_intents_last_executed ON intents(last_executed_at);

   -- DOWN (rollback)
   DROP INDEX idx_intents_last_executed;
   ALTER TABLE intents DROP COLUMN last_executed_at;
   ```

   **Step 2: Update ORM model** (`src/models/intent.rs`)
   ```rust
   #[derive(Debug, Clone, sqlx::FromRow)]
   pub struct Intent {
     pub id: String,
     pub name: String,
     #[sqlx(default)]
     pub last_executed_at: Option<DateTime<Utc>>,
   }
   ```

   **Step 3: Validate consistency** (before committing)
   ```bash
   sqlx prepare --database-url $DATABASE_URL  # Type-check all queries
   cargo test models::intent::  # Test ORM model
   ```

3. **Migration rules (non-negotiable):**
   - Every migration is version-locked by timestamp (never rename)
   - Migrations are immutable (never edit applied migrations)
   - UP and DOWN must always be present (rollback must work)
   - Data migrations must handle all existing data (no partial updates)
   - New columns with NOT NULL require defaults for existing rows
   - Foreign key changes must account for existing references
   - Indexes must be created on all foreign key columns
   - Constraint additions must validate existing data first

4. **ORM model rules:**
   - Every database column must have an ORM field (or be explicitly ignored)
   - Every ORM field must map to a database column (no phantom fields)
   - Field types must match database column types exactly
   - Required ORM fields must match NOT NULL constraints
   - Default values in ORM must match database defaults
   - Validation rules must enforce database constraints

## "Migration failed" debugging order (before touching code)

1. **What's the actual error?**
   ```bash
   sqlx migrate run --database-url $DATABASE_URL
   # Shows which migration failed and why
   # Common: foreign key exists, constraint violation, data type incompatibility
   ```

2. **Is the schema consistent before migration?**
   ```bash
   sqlx database info --database-url $DATABASE_URL
   # Shows current schema state
   # Check for unexpected tables/columns
   ```

3. **Can the migration roll back?**
   ```bash
   sqlx migrate revert --database-url $DATABASE_URL
   # Should revert without error
   # If fails: DOWN clause is broken
   ```

4. **Do ORM models match current schema?**
   ```bash
   cargo test models::schema_validation -- --nocapture
   # Should show field↔column mappings
   # If mismatch: update ORM models
   ```

5. **Is there conflicting data?**
   ```bash
   # For constraint violations:
   SELECT * FROM [table] WHERE [problematic_column] IS NULL;
   # If rows exist and column has NOT NULL constraint: delete them or add defaults
   ```

## "Data lost after migration" debugging

1. **Did the migration have a data migration clause?**
   ```bash
   grep -A 10 "ALTER TABLE" db/migrations/[failed_migration].sql
   # Should show how data was transformed
   # If just DROP COLUMN: data is gone (recovery needs backup)
   ```

2. **Was a backup taken before migration?**
   ```bash
   # Always backup before schema changes:
   # mysqldump [db] > backup_before_[timestamp].sql
   # Restore if needed: mysql [db] < backup_before_[timestamp].sql
   ```

3. **Check for orphaned rows:**
   ```sql
   -- Find rows that would violate new constraints
   SELECT * FROM [table] WHERE [new_column] IS NULL AND [new_column] NOT NULL;
   ```

## "Query errors after schema change" debugging

1. **Is the ORM model outdated?**
   ```bash
   cargo build
   # Compiler errors will show field mismatches
   # Type mismatches mean ORM model ≠ database
   ```

2. **Are queries referencing removed columns?**
   ```bash
   grep -r "[removed_column]" src/
   # Remove all references
   ```

3. **Run ORM model validation:**
   ```bash
   cargo test models:: -- --include-ignored --nocapture
   # Shows field→column mappings for all models
   ```

## Definition of done for database schema work

- [ ] Migration validation passes: `sqlx prepare --database-url $DATABASE_URL`
- [ ] ORM models match schema: `cargo test models::schema_validation`
- [ ] Migration UP and DOWN both execute successfully
- [ ] Data migration preserves or transforms data correctly
- [ ] Foreign keys and constraints enforce data integrity
- [ ] All queries type-check: `cargo build` with no errors
- [ ] Indexes created on frequently-queried columns
- [ ] `docs/DATABASE_SCHEMA.md` updated with table/column descriptions
- [ ] Schema change backlog includes steps for production rollout
- [ ] Commit includes migration file + ORM model changes together

---

**Related:** [[desktop-sidecar-communication]] (data changes must sync across
processes), [[voice-pipeline-integrity]] (voice history/metadata stored in DB)
