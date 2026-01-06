# Database Migrations Guide

This document describes how to manage database schema changes for the Trip Service using `golang-migrate`.

## Overview

We use a versioned migration approach to ensure consistency across all environments (local, dev, prod). Migrations are handled by the `trip-migrations` service defined in `docker-compose.yaml`.

## File Structure

Migrations are located in `trip-service/db/migrations/`:
- `XXX_name.up.sql`: Script to apply changes (e.g., create tables, types).
- `XXX_name.down.sql`: Script to revert changes (e.g., drop tables, types).

## How it Works

### Automatic Execution
When you run `docker compose up`, the `trip-migrations` service automatically applies all pending migrations before the main application starts. It tracks the current schema state in the `schema_migrations` table.

### Manual Rollback
If you need to revert the last applied migration, run the following command from the `trip-service` directory:

```bash
docker compose run --rm trip-migrations -path=/migrations/ -database "$DB_URL" down 1

## Creating New Migrations

When adding new tables or changing existing ones:

1. **Create a new pair of files** with an incremental prefix:
   * `002_add_index.up.sql`
   * `002_add_index.down.sql`
2. **Ensure reversibility**: The `down.sql` script must exactly reverse the actions of the `up.sql` script to maintain database integrity.

### Example Structure:
* **up.sql**: `CREATE TABLE users (...);`
* **down.sql**: `DROP TABLE users;`

---

## Troubleshooting

### Dirty Database
If a migration fails (e.g., due to a syntax error), the database is marked as **"dirty"** in the `schema_migrations` table. This prevents further migrations until resolved.

**To fix this:**

1. **Fix the error** in your SQL script.
2. **Force the version** back to the last stable state using the following command:

```bash
migrate -path migrations/ -database "postgres://localhost:5432/db_name?sslmode=disable" force <VERSION_NUMBER>