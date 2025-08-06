# CIRIS Agent Troubleshooting Guide

Comprehensive troubleshooting guide for CIRIS Agent deployment and operation issues.

## Table of Contents

- [Quick Diagnostic Commands](#quick-diagnostic-commands)
- [Common Issues](#common-issues)
- [Service-Specific Issues](#service-specific-issues)
- [Performance Issues](#performance-issues)
- [Security Issues](#security-issues)
- [Configuration Issues](#configuration-issues)
- [Emergency Procedures](#emergency-procedures)

## Quick Diagnostic Commands

### System Health Check
```bash
#!/bin/bash
# quick_health_check.sh

echo "=== CIRIS Agent Quick Health Check ==="

# Check Python environment
echo "Python version: $(python --version)"
echo "CIRIS Agent location: $(which python)"

# Check key environment variables
echo "Environment variables:"
echo "  OPENAI_API_KEY: $(if [ -n "$OPENAI_API_KEY" ]; then echo "SET (${#OPENAI_API_KEY} chars)"; else echo "NOT SET"; fi)"
echo "  DISCORD_BOT_TOKEN: $(if [ -n "$DISCORD_BOT_TOKEN" ]; then echo "SET (${#DISCORD_BOT_TOKEN} chars)"; else echo "NOT SET"; fi)"
echo "  SECRETS_MASTER_KEY: $(if [ -n "$SECRETS_MASTER_KEY" ]; then echo "SET (${#SECRETS_MASTER_KEY} chars)"; else echo "NOT SET"; fi)"

# Check database files
echo "Database files:"
echo "  Main DB: $(if [ -f "data/ciris_engine.db" ]; then echo "EXISTS"; else echo "MISSING"; fi)"
echo "  Secrets DB: $(if [ -f "secrets.db" ]; then echo "EXISTS"; else echo "MISSING"; fi)"

# Check configuration
echo "Configuration:"
echo "  Base config: $(if [ -f "config/base.yaml" ]; then echo "EXISTS"; else echo "MISSING"; fi)"
echo "  Production config: $(if [ -f "config/production.yaml" ]; then echo "EXISTS"; else echo "MISSING"; fi)"

# Check logs
echo "Recent log entries:"
if [ -f "logs/latest.log" ]; then
    tail -5 logs/latest.log
else
    echo "  No log file found"
fi

# Check process status
echo "CIRIS processes:"
pgrep -fl "python.*main.py" || echo "  No CIRIS processes running"
```

### Log Analysis
```bash
#!/bin/bash
# analyze_logs.sh

LOG_FILE="logs/latest.log"
AUDIT_FILE="audit_logs.jsonl"

if [ ! -f "$LOG_FILE" ]; then
    echo "Log file not found: $LOG_FILE"
    exit 1
fi

echo "=== CIRIS Agent Log Analysis ==="

# Count log levels
echo "Log levels (last 1000 entries):"
tail -1000 "$LOG_FILE" | cut -d' ' -f3 | sort | uniq -c | sort -nr

# Recent errors
echo "Recent errors:"
tail -1000 "$LOG_FILE" | grep -i "error\|exception\|failed" | tail -5

# Service status
echo "Service status indicators:"
tail -1000 "$LOG_FILE" | grep -i "service.*start\|service.*stop\|service.*error" | tail -5

# Memory/resource warnings
echo "Resource warnings:"
tail -1000 "$LOG_FILE" | grep -i "memory\|cpu\|resource\|limit" | tail -3

# Security events
if [ -f "$AUDIT_FILE" ]; then
    echo "Recent security events:"
    tail -5 "$AUDIT_FILE" | jq -r '.action_type // "UNKNOWN"' | sort | uniq -c
fi
```

## Common Issues

### 1. Agent Won't Start

**Symptoms**: Agent fails to start, immediate exit, or startup errors

**Diagnostic Steps**:
```bash
# Check Python dependencies
pip list | grep -E "(openai|discord|pydantic|asyncio)"

# Verify configuration syntax
python -c "
import yaml
try:
    with open('config/base.yaml') as f:
        yaml.safe_load(f)
    print('✅ Configuration syntax valid')
except Exception as e:
    print(f'❌ Configuration error: {e}')
"

# Test basic imports
python -c "
try:
    from ciris_engine.runtime.ciris_runtime import CIRISRuntime
    print('✅ Core imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
"
```

**Common Solutions**:
- **Missing dependencies**: Run `pip install -r requirements.txt`
- **Invalid configuration**: Check YAML syntax and required fields
- **Environment variables**: Ensure all required env vars are set
- **File permissions**: Check database and key file permissions

### 2. Database Connection Errors

**Symptoms**: SQLite errors, "database is locked", permission denied

**Diagnostic Steps**:
```bash
# Check database file permissions
ls -la data/ciris_engine.db secrets.db

# Test database connection
python -c "
import sqlite3
try:
    conn = sqlite3.connect('data/ciris_engine.db')
    conn.execute('SELECT 1').fetchone()
    conn.close()
    print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database error: {e}')
"

# Check for database locks
lsof data/ciris_engine.db || echo "No locks found"
```

**Common Solutions**:
- **Permission denied**: `chmod 600 data/ciris_engine.db`
- **Database locked**: Kill any hanging processes, restart agent
- **Corrupted database**: Restore from backup or reinitialize
- **Disk space**: Check available disk space with `df -h`

### 3. Authentication Failures

**Symptoms**: "Invalid API key", "Authentication failed", 401 errors

**Diagnostic Steps**:
```bash
# Test OpenAI API key
python -c "
import openai
import os
openai.api_key = os.getenv('OPENAI_API_KEY')
try:
    models = openai.Model.list()
    print('✅ OpenAI API key valid')
except Exception as e:
    print(f'❌ OpenAI API error: {e}')
"

# Test Discord token
python -c "
import discord
import os
import asyncio

async def test_discord():
    try:
        client = discord.Client()
        await client.login(os.getenv('DISCORD_BOT_TOKEN'))
        await client.close()
        print('✅ Discord token valid')
    except Exception as e:
        print(f'❌ Discord token error: {e}')

asyncio.run(test_discord())
"
```

**Common Solutions**:
- **Invalid API key**: Verify key in environment variables
- **Expired token**: Generate new API key/token
- **Network issues**: Check internet connectivity and firewall
- **Rate limiting**: Wait and reduce request frequency

### 4. Memory Issues

**Symptoms**: Out of memory errors, slow performance, high memory usage

**Diagnostic Steps**:
```bash
# Check system memory
free -h

# Check process memory usage
ps aux | grep python | grep main.py

# Monitor memory usage over time
top -p $(pgrep -f "python.*main.py") -d 5
```

**Common Solutions**:
- **Reduce buffer sizes**: Lower telemetry and processing buffers
- **Limit active thoughts**: Reduce `max_active_thoughts` in config
- **Enable resource limits**: Configure memory budgets
- **Restart service**: Periodic restarts to clear memory leaks

### 5. Performance Issues

**Symptoms**: Slow responses, high CPU usage, timeouts

**Diagnostic Steps**:
```bash
# Check CPU usage
top -p $(pgrep -f "python.*main.py")

# Check I/O wait
iostat -x 1 5

# Profile the application
python -m cProfile main.py --mode cli --profile default
```

**Common Solutions**:
- **Increase timeouts**: Adjust LLM and network timeouts
- **Reduce concurrent processing**: Lower max active tasks/thoughts
- **Optimize database**: Run `VACUUM` and `ANALYZE` on SQLite
- **Enable circuit breakers**: Implement failure protection

## Service-Specific Issues

### Secrets Management Issues

**Symptoms**: Secrets not detected, encryption errors, access denied

**Diagnostic Steps**:
```bash
# Test secrets encryption key
python -c "
import base64
import os
key = os.getenv('SECRETS_MASTER_KEY')
if key:
    try:
        decoded = base64.b64decode(key)
        print(f'✅ Secrets key valid ({len(decoded)} bytes)')
    except Exception as e:
        print(f'❌ Secrets key invalid: {e}')
else:
    print('❌ SECRETS_MASTER_KEY not set')
"

# Test secrets detection
python -c "
from ciris_engine.secrets.filter import SecretsFilter
filter = SecretsFilter()
test_text = 'My API key is sk-test123456789'
result = filter.filter_content(test_text)
print(f'Detection result: {result}')
"
```

**Solutions**:
- **Generate new master key**: `openssl rand -base64 32`
- **Check permissions**: Verify database and key file access
- **Restart service**: Reload configuration and encryption keys
- **Clear cache**: Remove any cached encryption data

### Telemetry Issues

**Symptoms**: No metrics collected, telemetry errors, memory leaks

**Diagnostic Steps**:
```bash
# Check telemetry configuration
python -c "
from ciris_engine.config.config_loader import ConfigLoader
import asyncio
async def check():
    config = await ConfigLoader.load_config()
    print(f'Telemetry enabled: {config.telemetry.enabled}')
    print(f'Buffer size: {config.telemetry.buffer_size}')
asyncio.run(check())
"

# Monitor telemetry service
tail -f logs/latest.log | grep -i telemetry
```

**Solutions**:
- **Enable telemetry**: Set `telemetry.enabled: true` in config
- **Increase buffer size**: Adjust buffer sizes for high throughput
- **Check collectors**: Verify collector intervals and configurations
- **Monitor memory**: Watch for telemetry memory usage

### Audit Trail Issues

**Symptoms**: Signature verification fails, hash chain broken, audit errors

**Diagnostic Steps**:
```bash
# Verify audit keys
openssl rsa -in audit_keys/audit_private.pem -check -noout
openssl rsa -in audit_keys/audit_public.pem -pubin -text -noout

# Check audit database
sqlite3 ciris_audit.db ".schema audit_log_v2"

# Verify hash chain
python -c "
from ciris_engine.audit.verifier import AuditVerifier
verifier = AuditVerifier()
print(f'Hash chain valid: {verifier.verify_chain_integrity()}')
print(f'Signatures valid: {verifier.verify_signatures()}')
"
```

**Solutions**:
- **Regenerate keys**: Create new RSA key pair for signatures
- **Reset audit chain**: Initialize new hash chain (breaks history)
- **Check timestamps**: Ensure system clock is synchronized
- **Repair database**: Run SQLite integrity check and repair

### LLM Service Issues

**Symptoms**: API timeouts, rate limit errors, response quality issues

**Diagnostic Steps**:
```bash
# Test LLM connectivity
python -c "
from ciris_engine.adapters.openai_compatible_llm import OpenAICompatibleLLM
from ciris_engine.schemas.config_schemas_v1 import LLMServicesConfig
import asyncio

async def test():
    config = LLMServicesConfig()
    llm = OpenAICompatibleLLM(config)
    try:
        await llm.start()
        response = await llm.generate_response('Test message')
        print(f'✅ LLM response: {response[:50]}...')
        await llm.stop()
    except Exception as e:
        print(f'❌ LLM error: {e}')

asyncio.run(test())
"
```

**Solutions**:
- **Increase timeouts**: Adjust `timeout_seconds` in config
- **Reduce rate**: Lower request frequency, add delays
- **Check quotas**: Verify API usage limits and billing
- **Switch models**: Try different model names or providers

## Performance Issues

### High Memory Usage

**Diagnosis**:
```bash
# Memory profiling
python -m memory_profiler main.py --mode cli --profile default

# Check for memory leaks
valgrind --tool=memcheck python main.py
```

**Solutions**:
```yaml
# Reduce memory usage in config
workflow:
  max_active_thoughts: 25  # Reduce from 50
  max_active_tasks: 5      # Reduce from 10

telemetry:
  buffer_size: 500         # Reduce from 1000

resources:
  budgets:
    memory:
      limit: 128           # Set appropriate limit
      action: "defer"      # Defer instead of crash
```

### Slow Response Times

**Diagnosis**:
```bash
# Profile response times
python -c "
import time
from ciris_engine.runtime.cli_runtime import CLIRuntime
import asyncio

async def profile():
    runtime = CLIRuntime()
    start = time.time()
    await runtime.initialize()
    init_time = time.time() - start
    print(f'Initialization time: {init_time:.2f}s')
    await runtime.shutdown()

asyncio.run(profile())
"
```

**Solutions**:
```yaml
# Optimize for speed
llm_services:
  openai:
    timeout_seconds: 15.0  # Reduce timeout
    model_name: "gpt-3.5-turbo"  # Use faster model

workflow:
  round_delay_seconds: 0.5  # Reduce delay
  max_rounds: 3            # Limit processing rounds

adaptive:
  circuit_breaker:
    failure_threshold: 2   # Fail fast
    reset_timeout: 60     # Quick recovery
```

### Database Performance

**Diagnosis**:
```bash
# Check database size and fragmentation
sqlite3 data/ciris_engine.db "PRAGMA integrity_check;"
sqlite3 data/ciris_engine.db "PRAGMA page_count; PRAGMA freelist_count;"

# Analyze slow queries
sqlite3 data/ciris_engine.db "PRAGMA compile_options;"
```

**Optimization**:
```bash
# Optimize database
sqlite3 data/ciris_engine.db "VACUUM;"
sqlite3 data/ciris_engine.db "ANALYZE;"
sqlite3 data/ciris_engine.db "PRAGMA optimize;"

# Enable WAL mode for better concurrency
sqlite3 data/ciris_engine.db "PRAGMA journal_mode=WAL;"
```

## Security Issues

### Secrets Not Detected

**Diagnosis**:
```python
# Test secrets detection
from ciris_engine.secrets.filter import SecretsFilter

filter = SecretsFilter()
test_cases = [
    "sk-1234567890abcdef",          # OpenAI key
    "xoxb-1234567890-abcdef",       # Slack token
    "ghp_1234567890abcdef",         # GitHub token
    "4532-1234-5678-9012",          # Credit card
]

for test in test_cases:
    result = filter.filter_content(f"My secret is {test}")
    print(f"'{test}' -> Detected: {len(result.secrets_detected) > 0}")
```

**Solutions**:
- **Update patterns**: Add custom detection patterns
- **Increase sensitivity**: Set threshold to "HIGH" or "CRITICAL"
- **Check configuration**: Verify secrets service is enabled
- **Test manually**: Use secrets CLI tools for testing

### Audit Integrity Failures

**Diagnosis**:
```python
# Comprehensive audit check
from ciris_engine.audit.verifier import AuditVerifier

verifier = AuditVerifier()

# Check each component
print(f"Hash chain: {verifier.verify_chain_integrity()}")
print(f"Signatures: {verifier.verify_signatures()}")
print(f"Tampering: {verifier.check_for_tampering()}")
print(f"Key validity: {verifier.verify_key_integrity()}")
```

**Solutions**:
- **Regenerate keys**: Create new audit key pair
- **Reset chain**: Initialize new hash chain (loses history)
- **Check system time**: Ensure NTP synchronization
- **Backup/restore**: Restore from known good backup

### Access Control Bypasses

**Diagnosis**:
```bash
# Check role assignments
python -c "
from ciris_engine.utils.profile_loader import load_profile
profile = load_profile('teacher')
print(f'Permitted actions: {profile.permitted_actions}')
print(f'Guardrails: {profile.guardrails_config}')
"
```

**Solutions**:
- **Review profiles**: Check agent profile configurations
- **Enable WA approval**: Require approval for critical changes
- **Audit logs**: Review access patterns in audit trail
- **Update permissions**: Restrict unnecessary capabilities

## Configuration Issues

### Invalid YAML Syntax

**Diagnosis**:
```bash
# Validate YAML files
python -c "
import yaml
import sys

files = ['config/base.yaml', 'config/production.yaml', 'ciris_profiles/default.yaml']
for file in files:
    try:
        with open(file) as f:
            yaml.safe_load(f)
        print(f'✅ {file}: Valid')
    except FileNotFoundError:
        print(f'⚠️  {file}: Not found')
    except yaml.YAMLError as e:
        print(f'❌ {file}: {e}')
        sys.exit(1)
"
```

**Solutions**:
- **Use YAML validator**: Online YAML validators for syntax checking
- **Check indentation**: Ensure consistent spaces (not tabs)
- **Quote strings**: Quote special characters and values
- **Validate structure**: Compare with working configuration files

### Environment Variable Issues

**Diagnosis**:
```bash
# Check all required environment variables
required_vars=(
    "OPENAI_API_KEY"
    "SECRETS_MASTER_KEY"
    "DISCORD_BOT_TOKEN"
    "LOG_LEVEL"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ $var: Not set"
    else
        echo "✅ $var: Set (${#!var} chars)"
    fi
done
```

**Solutions**:
- **Create .env file**: Use environment file for development
- **Check shell**: Ensure variables are exported
- **Verify encoding**: Check for special characters in values
- **Test loading**: Use config loader to verify variable loading

## Emergency Procedures

### Emergency Shutdown

```bash
#!/bin/bash
# emergency_shutdown.sh

echo "=== EMERGENCY SHUTDOWN PROCEDURE ==="

# Find CIRIS processes
PIDS=$(pgrep -f "python.*main.py")

if [ -z "$PIDS" ]; then
    echo "No CIRIS processes found"
    exit 0
fi

echo "Found CIRIS processes: $PIDS"

# Graceful shutdown (SIGTERM)
echo "Attempting graceful shutdown..."
kill -TERM $PIDS
sleep 10

# Check if processes stopped
REMAINING=$(pgrep -f "python.*main.py")
if [ -z "$REMAINING" ]; then
    echo "✅ Graceful shutdown successful"
    exit 0
fi

# Force shutdown (SIGKILL)
echo "Forcing shutdown..."
kill -KILL $REMAINING
sleep 2

# Verify shutdown
FINAL=$(pgrep -f "python.*main.py")
if [ -z "$FINAL" ]; then
    echo "✅ Force shutdown successful"
else
    echo "❌ Shutdown failed, processes still running: $FINAL"
    exit 1
fi
```

### Database Recovery

```bash
#!/bin/bash
# database_recovery.sh

echo "=== DATABASE RECOVERY PROCEDURE ==="

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup current databases
echo "Backing up current databases..."
cp data/ciris_engine.db "$BACKUP_DIR/" 2>/dev/null
cp secrets.db "$BACKUP_DIR/" 2>/dev/null
cp ciris_audit.db "$BACKUP_DIR/" 2>/dev/null

# Test database integrity
echo "Testing database integrity..."
if sqlite3 data/ciris_engine.db "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "✅ Main database integrity OK"
else
    echo "❌ Main database corrupted, attempting repair..."

    # Attempt repair
    sqlite3 data/ciris_engine.db ".recover" | sqlite3 data/ciris_engine_recovered.db
    mv data/ciris_engine.db data/ciris_engine_corrupted.db
    mv data/ciris_engine_recovered.db data/ciris_engine.db

    echo "Database recovery attempted"
fi

# Reinitialize if needed
if [ ! -f "data/ciris_engine.db" ] || ! sqlite3 data/ciris_engine.db "SELECT 1;" &>/dev/null; then
    echo "Reinitializing database..."
    python -c "
from ciris_engine.persistence.db.setup import initialize_database
initialize_database()
print('Database reinitialized')
"
fi

echo "Database recovery complete"
```

### Key Recovery

```bash
#!/bin/bash
# key_recovery.sh

echo "=== KEY RECOVERY PROCEDURE ==="

# This will invalidate all existing encrypted data
read -p "This will invalidate existing secrets. Continue? (y/N): " confirm
if [ "$confirm" != "y" ]; then
    echo "Recovery cancelled"
    exit 0
fi

# Backup existing keys
BACKUP_DIR="key_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r audit_keys "$BACKUP_DIR/" 2>/dev/null

# Generate new secrets master key
echo "Generating new secrets master key..."
openssl rand -base64 32 > new_secrets_master.key
echo "export SECRETS_MASTER_KEY=$(cat new_secrets_master.key)" > secrets_env.sh

# Generate new audit keys
echo "Generating new audit keys..."
mkdir -p audit_keys
openssl genrsa -out audit_keys/audit_private.pem 4096
openssl rsa -in audit_keys/audit_private.pem -pubout -out audit_keys/audit_public.pem
chmod 600 audit_keys/audit_private.pem
chmod 644 audit_keys/audit_public.pem

# Clear secrets database (encrypted data is now invalid)
rm -f secrets.db

echo "Key recovery complete"
echo "NOTE: All previously encrypted secrets are now invalid"
echo "Load new environment: source secrets_env.sh"
```

### System Reset

```bash
#!/bin/bash
# system_reset.sh

echo "=== SYSTEM RESET PROCEDURE ==="
echo "This will delete ALL data and configuration"
read -p "Are you sure? Type 'RESET' to confirm: " confirm

if [ "$confirm" != "RESET" ]; then
    echo "Reset cancelled"
    exit 0
fi

# Create backup
BACKUP_DIR="reset_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r data/ "$BACKUP_DIR/" 2>/dev/null
cp -r audit_keys/ "$BACKUP_DIR/" 2>/dev/null
cp *.db "$BACKUP_DIR/" 2>/dev/null
cp config/*.yaml "$BACKUP_DIR/" 2>/dev/null

# Stop services
./emergency_shutdown.sh

# Clear data
rm -rf data/
rm -f *.db
rm -f logs/*.log
rm -f audit_logs.jsonl

# Reinitialize
mkdir -p data
python -c "
from ciris_engine.persistence.db.setup import initialize_database
initialize_database()
print('System reset complete')
"

echo "System reset complete"
echo "Backup saved to: $BACKUP_DIR"
```

### Contact Support

When contacting support, please provide:

1. **System Information**:
   ```bash
   uname -a
   python --version
   pip list | grep -E "(ciris|openai|discord)"
   ```

2. **Configuration** (redacted):
   ```bash
   # Remove sensitive data before sharing
   sed 's/api_key.*/api_key: [REDACTED]/' config/production.yaml
   ```

3. **Logs**:
   ```bash
   # Last 100 lines of logs
   tail -100 logs/latest.log

   # Recent audit events
   tail -50 audit_logs.jsonl
   ```

4. **Error Details**:
   - Full error messages and stack traces
   - Steps to reproduce the issue
   - When the issue started occurring
   - Any recent configuration changes

Remember to sanitize all logs and configuration files before sharing to remove sensitive information like API keys, tokens, and secrets.
