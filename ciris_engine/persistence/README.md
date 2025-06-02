# persistence

This module contains the persistence components of the CIRIS engine.

## Database Migrations

The persistence layer uses a very small migration system based on numbered SQL
files located in `ciris_engine/persistence/migrations/`. On startup the runtime
runs all pending migrations in order and records them in the `schema_migrations`
table.

To add a new migration:

1. Create a new file in the migrations directory with a numeric prefix, e.g.
   `003_new_feature.sql`.
2. Write the SQL statements needed for the change. The file will be executed in
   a single transaction.
3. Incremental migrations will run automatically the next time the application
   starts or when `initialize_database()` is called in tests.

If a migration fails it is rolled back and the database remains unchanged.
