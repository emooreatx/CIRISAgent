# Data Storage Directory

The data directory serves as the default storage location for CIRIS agent runtime data files, including SQLite databases and persistent storage components.

## Contents

### Database Files

- **`ciris_engine.db`** - Main agent database containing:
  - Task and thought persistence
  - Graph memory storage
  - Correlation data
  - Processing queue items
  - System state information

- **`ciris_engine_secrets.db`** - Encrypted secrets storage database containing:
  - Encrypted secret records
  - Secret metadata and references
  - Access audit logs
  - Encryption key management data

## Database Schema

The databases are managed through the persistence layer and include tables defined in migration files:

- **Migration 001**: Initial schema setup (tasks, thoughts, correlations)
- **Migration 002**: Retry status tracking 
- **Migration 003**: Signed audit trail implementation

## Configuration

### Default Location

The data directory is configurable through the application configuration:

```yaml
database:
  db_filename: "ciris_engine.db"
  data_directory: "data"
  graph_memory_filename: "graph_memory.db"
```

### Environment Variables

- `CIRIS_DB_PATH` - Override default database path
- `CIRIS_DATA_DIR` - Override default data directory location

## Security

### Database Protection

- **File Permissions**: Database files should have restricted permissions (600)
- **Encryption**: Secrets database uses AES-256-GCM encryption
- **Access Control**: All database access is mediated through service interfaces
- **Audit Logging**: All database operations are logged through the audit system

### Backup Considerations

- Database files contain sensitive agent state and encrypted secrets
- Backup procedures should maintain encryption and access controls
- Regular backup verification is recommended for data integrity

## Usage

### Database Initialization

Databases are automatically created and migrated on first run:

```python
from ciris_engine.persistence.db.core import get_db_connection
from ciris_engine.persistence.db.migration_runner import run_migrations

# Initialize database with migrations
connection = get_db_connection()
run_migrations(connection)
```

### Data Directory Management

```python
from ciris_engine.config import get_config
import os

config = get_config()
data_dir = config.database.data_directory

# Ensure data directory exists
os.makedirs(data_dir, exist_ok=True)

# Get full database path
db_path = os.path.join(data_dir, config.database.db_filename)
```

## Maintenance

### Database Cleanup

The maintenance service provides automated cleanup:

- Task completion cleanup
- Thought archive management  
- Log rotation
- Unused correlation removal

### Monitoring

Monitor database file sizes and growth:

```bash
# Check database sizes
ls -lh ciris_engine/data/*.db

# Check database integrity (SQLite)
sqlite3 ciris_engine/data/ciris_engine.db "PRAGMA integrity_check;"
```

## Troubleshooting

### Common Issues

**Database Locked Errors**
- Ensure proper connection cleanup in all services
- Check for long-running transactions
- Verify no orphaned connections

**Permission Denied**
- Check file permissions on database files
- Verify data directory is writable
- Ensure proper user ownership

**Schema Migration Failures**
- Check migration logs for specific errors
- Verify database file is not corrupted
- Consider backup restoration if needed

### Recovery Procedures

**Database Corruption**
1. Stop all agent processes
2. Backup corrupted database
3. Restore from recent backup or recreate
4. Run integrity checks after restoration

**Secret Database Issues**
- Secret database corruption requires careful handling
- Contact system administrator for secret recovery procedures
- Never attempt manual secret database repairs

## Integration

### Service Integration

The data directory integrates with:

- **Persistence Layer**: Core database operations and migrations
- **Secrets Service**: Encrypted secrets storage and retrieval
- **Audit Service**: Action logging and integrity verification
- **Memory Service**: Graph storage and recall operations
- **Configuration**: Database path and settings management

### Docker Deployment

When deploying with Docker, mount the data directory as a volume:

```yaml
volumes:
  - ./data:/app/ciris_engine/data
```

This ensures database persistence across container restarts and updates.

---

The data directory provides secure, persistent storage for all CIRIS agent runtime data while maintaining proper access controls and audit trails.