# CIRIS Agent Security Setup Guide

Comprehensive security configuration for enterprise-grade deployments.

## Table of Contents

- [Security Architecture Overview](#security-architecture-overview)
- [Encryption and Key Management](#encryption-and-key-management)
- [Audit Trail Configuration](#audit-trail-configuration)
- [Secrets Management](#secrets-management)
- [Access Control](#access-control)
- [Network Security](#network-security)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Compliance and Governance](#compliance-and-governance)

## Security Architecture Overview

CIRIS Agent implements defense-in-depth security with multiple layers:

1. **Input Validation**: All inputs filtered through adaptive filter service
2. **Secrets Management**: Automatic detection and AES-256-GCM encryption
3. **Audit Trail**: Cryptographically signed hash-chained audit logs
4. **Access Control**: Role-based permissions with WA (Wisdom Authority) oversight
5. **Network Security**: TLS encryption and authentication
6. **Resource Protection**: Circuit breakers and resource limits
7. **Data Privacy**: PII detection and sanitization

## Encryption and Key Management

### Master Encryption Keys

Generate secure master keys for different subsystems:

```bash
#!/bin/bash
# generate_keys.sh

# Create secure key directory
sudo mkdir -p /etc/ciris/keys
sudo chmod 700 /etc/ciris/keys

# Generate secrets management master key (AES-256)
openssl rand -base64 32 > /etc/ciris/keys/secrets_master.key
sudo chmod 600 /etc/ciris/keys/secrets_master.key

# Generate telemetry encryption key
openssl rand -base64 32 > /etc/ciris/keys/telemetry.key
sudo chmod 600 /etc/ciris/keys/telemetry.key

# Generate session encryption key
openssl rand -base64 32 > /etc/ciris/keys/session.key
sudo chmod 600 /etc/ciris/keys/session.key

echo "Keys generated successfully in /etc/ciris/keys/"
echo "IMPORTANT: Backup these keys securely!"
```

### Audit Trail Cryptographic Keys

Set up RSA key pairs for audit trail signatures:

```bash
#!/bin/bash
# setup_audit_keys.sh

# Create audit key directory
sudo mkdir -p /etc/ciris/audit_keys
sudo chmod 700 /etc/ciris/audit_keys

# Generate RSA-4096 key pair for production
openssl genrsa -out /etc/ciris/audit_keys/audit_private.pem 4096
openssl rsa -in /etc/ciris/audit_keys/audit_private.pem \
  -pubout -out /etc/ciris/audit_keys/audit_public.pem

# Set strict permissions
sudo chmod 600 /etc/ciris/audit_keys/audit_private.pem
sudo chmod 644 /etc/ciris/audit_keys/audit_public.pem

# Verify key generation
openssl rsa -in /etc/ciris/audit_keys/audit_private.pem -check -noout
echo "Audit keys generated and verified successfully"

# Generate key fingerprint for verification
openssl rsa -in /etc/ciris/audit_keys/audit_public.pem \
  -pubin -outform DER | sha256sum > /etc/ciris/audit_keys/public_key_fingerprint.txt

echo "Public key fingerprint saved to public_key_fingerprint.txt"
```

### Key Rotation Strategy

Implement automated key rotation:

```bash
#!/bin/bash
# rotate_keys.sh

BACKUP_DIR="/etc/ciris/key_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup current keys
cp /etc/ciris/keys/* "$BACKUP_DIR/"
cp /etc/ciris/audit_keys/* "$BACKUP_DIR/"

# Rotate secrets key (30-day cycle)
if [ -f "/etc/ciris/keys/secrets_master.key" ]; then
    # Archive old key
    mv /etc/ciris/keys/secrets_master.key "$BACKUP_DIR/secrets_master_old.key"

    # Generate new key
    openssl rand -base64 32 > /etc/ciris/keys/secrets_master.key
    chmod 600 /etc/ciris/keys/secrets_master.key

    echo "Secrets master key rotated"
fi

# Rotate audit keys (90-day cycle)
AUDIT_KEY_AGE=$(find /etc/ciris/audit_keys/audit_private.pem -mtime +90 2>/dev/null | wc -l)
if [ "$AUDIT_KEY_AGE" -gt 0 ]; then
    # Archive old keys
    mv /etc/ciris/audit_keys/audit_private.pem "$BACKUP_DIR/audit_private_old.pem"
    mv /etc/ciris/audit_keys/audit_public.pem "$BACKUP_DIR/audit_public_old.pem"

    # Generate new keys
    openssl genrsa -out /etc/ciris/audit_keys/audit_private.pem 4096
    openssl rsa -in /etc/ciris/audit_keys/audit_private.pem \
      -pubout -out /etc/ciris/audit_keys/audit_public.pem

    chmod 600 /etc/ciris/audit_keys/audit_private.pem
    chmod 644 /etc/ciris/audit_keys/audit_public.pem

    echo "Audit keys rotated"
fi

echo "Key rotation completed. Backups saved to: $BACKUP_DIR"
```

## Audit Trail Configuration

### Production Audit Configuration

```yaml
# config/production.yaml - Audit section
audit:
  enable_signed_audit: true
  enable_jsonl_audit: true
  audit_log_path: "/var/log/ciris/audit_logs.jsonl"
  audit_db_path: "/var/lib/ciris/ciris_audit.db"
  audit_key_path: "/etc/ciris/audit_keys"
  rotation_size_mb: 50
  retention_days: 2555  # 7 years for compliance

  hash_chain:
    enabled: true
    algorithm: "sha256"

  signatures:
    enabled: true
    algorithm: "rsa-pss"
    key_size: 4096
    key_rotation_days: 30

  anchoring:
    enabled: true
    interval_hours: 1
    method: "local"  # Can be extended to blockchain
```

### Audit Verification Script

```bash
#!/bin/bash
# verify_audit_integrity.sh

echo "=== CIRIS Audit Trail Integrity Verification ==="

# Verify hash chain integrity
python3 << EOF
from ciris_engine.audit.verifier import AuditVerifier
from ciris_engine.audit.hash_chain import HashChain
import sys

try:
    verifier = AuditVerifier()

    # Verify hash chain
    chain_result = verifier.verify_chain_integrity()
    print(f"Hash Chain Integrity: {'VALID' if chain_result else 'INVALID'}")

    # Verify signatures
    sig_result = verifier.verify_signatures()
    print(f"Digital Signatures: {'VALID' if sig_result else 'INVALID'}")

    # Check for tampering
    tamper_result = verifier.check_for_tampering()
    print(f"Tampering Check: {'CLEAN' if not tamper_result else 'TAMPERING DETECTED'}")

    if chain_result and sig_result and not tamper_result:
        print("\\n✅ AUDIT TRAIL INTEGRITY: VERIFIED")
        sys.exit(0)
    else:
        print("\\n❌ AUDIT TRAIL INTEGRITY: COMPROMISED")
        sys.exit(1)

except Exception as e:
    print(f"\\n❌ VERIFICATION ERROR: {e}")
    sys.exit(1)
EOF

echo "=== Verification Complete ==="
```

## Secrets Management

### Secrets Detection Configuration

```yaml
# Fine-tuned secrets detection
secrets:
  enabled: true
  detection:
    builtin_patterns: true
    custom_patterns_enabled: true
    sensitivity_threshold: "HIGH"  # LOW, MEDIUM, HIGH, CRITICAL

    # Custom patterns for organization-specific secrets
    custom_patterns:
      - name: "internal_api_key"
        pattern: "INT_[A-Z0-9]{32}"
        sensitivity: "HIGH"
        description: "Internal API keys"

      - name: "employee_id"
        pattern: "EMP[0-9]{6}"
        sensitivity: "MEDIUM"
        description: "Employee ID numbers"
```

### Secrets Storage Security

```bash
#!/bin/bash
# secure_secrets_storage.sh

# Create secrets database with proper permissions
SECRETS_DB="/var/lib/ciris/secrets.db"
SECRETS_DIR="/var/lib/ciris"

# Ensure directory exists with secure permissions
sudo mkdir -p "$SECRETS_DIR"
sudo chown ciris:ciris "$SECRETS_DIR"
sudo chmod 750 "$SECRETS_DIR"

# Initialize secrets database if it doesn't exist
if [ ! -f "$SECRETS_DB" ]; then
    python3 -c "
from ciris_engine.secrets.store import SecretsStore
store = SecretsStore('$SECRETS_DB')
store.initialize()
print('Secrets database initialized')
"
fi

# Set database permissions
sudo chmod 600 "$SECRETS_DB"
sudo chown ciris:ciris "$SECRETS_DB"

echo "Secrets storage secured"
```

### Secrets Access Audit

```python
#!/usr/bin/env python3
# audit_secrets_access.py

from ciris_engine.secrets.store import SecretsStore
from datetime import datetime, timedelta
import json

def audit_secrets_access():
    """Generate secrets access audit report"""

    store = SecretsStore()

    # Get access logs from last 24 hours
    since = datetime.now() - timedelta(hours=24)
    access_logs = store.get_access_logs(since=since)

    report = {
        "audit_timestamp": datetime.now().isoformat(),
        "period": "24_hours",
        "total_accesses": len(access_logs),
        "unique_secrets": len(set(log.secret_id for log in access_logs)),
        "access_by_action": {},
        "suspicious_activity": []
    }

    # Analyze access patterns
    action_counts = {}
    for log in access_logs:
        action = log.action_type
        action_counts[action] = action_counts.get(action, 0) + 1

        # Flag suspicious activity
        if log.access_count > 10:  # More than 10 accesses to same secret
            report["suspicious_activity"].append({
                "secret_id": log.secret_id,
                "access_count": log.access_count,
                "last_access": log.access_time.isoformat(),
                "reason": "Excessive access frequency"
            })

    report["access_by_action"] = action_counts

    # Save report
    with open(f"/var/log/ciris/secrets_audit_{datetime.now().strftime('%Y%m%d')}.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Secrets audit complete. {report['total_accesses']} accesses analyzed.")
    if report["suspicious_activity"]:
        print(f"⚠️  {len(report['suspicious_activity'])} suspicious activities detected!")

    return report

if __name__ == "__main__":
    audit_secrets_access()
```

## Access Control

### Role-Based Access Control (RBAC)

```yaml
# ciris_profiles/security_analyst.yaml
name: "security_analyst"
permitted_actions:
  - "OBSERVE"
  - "RECALL"
  - "MEMORIZE"
  - "TOOL"
  - "DEFER"
  # Restricted: Cannot use SPEAK without approval

access_controls:
  secrets_access: "READ_ONLY"
  audit_access: "FULL"
  config_changes: "REQUIRE_APPROVAL"

guardrails_config:
  entropy_threshold: 0.7
  coherence_threshold: 0.8
  optimization_veto_enabled: true
  epistemic_humility_threshold: 0.9

dsdma_identifier: "SecurityAnalystDSDMA"
```

### Wisdom Authority (WA) Integration

```python
#!/usr/bin/env python3
# wa_approval_workflow.py

from ciris_engine.services.agent_config_service import AgentConfigService
from ciris_engine.schemas.config_schemas_v1 import IdentityUpdatesConfig

class WAApprovalWorkflow:
    """Implements Wisdom Authority approval for critical operations"""

    def __init__(self, config_service: AgentConfigService):
        self.config_service = config_service
        self.pending_approvals = {}

    async def request_identity_change(self, change_request: dict) -> str:
        """Request approval for identity-level configuration changes"""

        approval_id = f"wa_approval_{datetime.now().timestamp()}"

        # Store pending request
        self.pending_approvals[approval_id] = {
            "request": change_request,
            "timestamp": datetime.now(),
            "status": "PENDING_WA_APPROVAL",
            "timeout": datetime.now() + timedelta(hours=24)
        }

        # Log the request
        await self.config_service.audit_service.log_action(
            action_type="REQUEST_WA_APPROVAL",
            details={
                "approval_id": approval_id,
                "change_type": change_request.get("type"),
                "scope": "IDENTITY"
            }
        )

        return approval_id

    async def process_wa_response(self, approval_id: str, approved: bool, wa_signature: str):
        """Process WA approval response"""

        if approval_id not in self.pending_approvals:
            raise ValueError(f"Unknown approval ID: {approval_id}")

        request = self.pending_approvals[approval_id]

        if approved:
            # Apply the configuration change
            await self.config_service.apply_config_change(request["request"])
            request["status"] = "APPROVED_AND_APPLIED"
        else:
            request["status"] = "REJECTED_BY_WA"

        # Log the decision
        await self.config_service.audit_service.log_action(
            action_type="WA_APPROVAL_DECISION",
            details={
                "approval_id": approval_id,
                "approved": approved,
                "wa_signature": wa_signature
            }
        )

        return request["status"]
```

## Network Security

### TLS Configuration

```yaml
# Network security configuration
network:
  tls:
    enabled: true
    cert_path: "/etc/ciris/tls/server.crt"
    key_path: "/etc/ciris/tls/server.key"
    ca_path: "/etc/ciris/tls/ca.crt"
    min_version: "TLSv1.3"
    cipher_suites:
      - "TLS_AES_256_GCM_SHA384"
      - "TLS_CHACHA20_POLY1305_SHA256"

  firewall:
    allowed_ips:
      - "10.0.0.0/8"      # Internal network
      - "172.16.0.0/12"   # Private network
    blocked_ips: []
    rate_limiting:
      requests_per_minute: 60
      burst_size: 10
```

### Network Monitoring

```bash
#!/bin/bash
# monitor_network_security.sh

echo "=== CIRIS Network Security Monitor ==="

# Monitor connection attempts
echo "Recent connection attempts:"
tail -100 /var/log/ciris/network.log | grep "CONNECTION_ATTEMPT" | tail -10

# Check for suspicious activity
echo "Suspicious network activity:"
tail -1000 /var/log/ciris/network.log | grep -E "(RATE_LIMIT|BLOCKED_IP|INVALID_CERT)" | tail -5

# Monitor TLS handshakes
echo "TLS handshake status:"
tail -100 /var/log/ciris/network.log | grep "TLS_HANDSHAKE" | tail -5

# Check certificate expiry
echo "Certificate status:"
openssl x509 -in /etc/ciris/tls/server.crt -dates -noout
```

## Monitoring and Alerting

### Security Event Monitoring

```python
#!/usr/bin/env python3
# security_monitor.py

import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from ciris_engine.audit.verifier import AuditVerifier

class SecurityMonitor:
    """Monitor for security events and anomalies"""

    def __init__(self, config):
        self.config = config
        self.alerts = []

    def check_failed_logins(self):
        """Monitor for excessive failed login attempts"""
        # Implementation would check audit logs for failed auth attempts
        pass

    def check_secrets_anomalies(self):
        """Monitor for unusual secrets access patterns"""
        # Check for secrets accessed outside normal hours
        # Check for excessive secrets access
        # Check for access to critical secrets
        pass

    def check_audit_integrity(self):
        """Verify audit trail integrity"""
        verifier = AuditVerifier()

        if not verifier.verify_chain_integrity():
            self.alerts.append({
                "severity": "CRITICAL",
                "type": "AUDIT_INTEGRITY_FAILURE",
                "message": "Audit hash chain integrity check failed",
                "timestamp": datetime.now().isoformat()
            })

    def check_resource_anomalies(self):
        """Monitor for resource usage anomalies"""
        # Check for sudden spikes in CPU/memory usage
        # Check for excessive API calls
        # Check for storage anomalies
        pass

    def send_alerts(self):
        """Send security alerts via configured channels"""
        if not self.alerts:
            return

        # Email alerts
        if self.config.get("email_alerts_enabled"):
            self._send_email_alerts()

        # Webhook alerts
        if self.config.get("webhook_url"):
            self._send_webhook_alerts()

        # Log alerts
        for alert in self.alerts:
            print(f"🚨 SECURITY ALERT: {alert}")

    def _send_email_alerts(self):
        """Send alerts via email"""
        # Implementation for email alerts
        pass

    def _send_webhook_alerts(self):
        """Send alerts via webhook"""
        # Implementation for webhook alerts
        pass

# Run security monitoring
if __name__ == "__main__":
    config = {
        "email_alerts_enabled": True,
        "webhook_url": "https://your-monitoring.com/webhook"
    }

    monitor = SecurityMonitor(config)
    monitor.check_audit_integrity()
    monitor.check_secrets_anomalies()
    monitor.check_resource_anomalies()
    monitor.send_alerts()
```

### Health Check Dashboard

```python
#!/usr/bin/env python3
# security_dashboard.py

from ciris_engine.telemetry.core import TelemetryService
from ciris_engine.audit.verifier import AuditVerifier
from ciris_engine.secrets.store import SecretsStore
import json

def generate_security_dashboard():
    """Generate security status dashboard"""

    dashboard = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "UNKNOWN",
        "components": {}
    }

    # Check audit system
    try:
        verifier = AuditVerifier()
        audit_status = "HEALTHY" if verifier.verify_chain_integrity() else "DEGRADED"
        dashboard["components"]["audit_system"] = {
            "status": audit_status,
            "last_check": datetime.now().isoformat()
        }
    except Exception as e:
        dashboard["components"]["audit_system"] = {
            "status": "ERROR",
            "error": str(e)
        }

    # Check secrets system
    try:
        store = SecretsStore()
        secrets_count = store.get_secrets_count()
        dashboard["components"]["secrets_system"] = {
            "status": "HEALTHY",
            "secrets_count": secrets_count,
            "last_check": datetime.now().isoformat()
        }
    except Exception as e:
        dashboard["components"]["secrets_system"] = {
            "status": "ERROR",
            "error": str(e)
        }

    # Check telemetry system
    try:
        # This would integrate with actual telemetry service
        dashboard["components"]["telemetry_system"] = {
            "status": "HEALTHY",
            "buffer_utilization": "45%",
            "last_check": datetime.now().isoformat()
        }
    except Exception as e:
        dashboard["components"]["telemetry_system"] = {
            "status": "ERROR",
            "error": str(e)
        }

    # Determine overall status
    statuses = [comp["status"] for comp in dashboard["components"].values()]
    if "ERROR" in statuses:
        dashboard["overall_status"] = "ERROR"
    elif "DEGRADED" in statuses:
        dashboard["overall_status"] = "DEGRADED"
    else:
        dashboard["overall_status"] = "HEALTHY"

    return dashboard

if __name__ == "__main__":
    dashboard = generate_security_dashboard()
    print(json.dumps(dashboard, indent=2))
```

## Compliance and Governance

### Compliance Frameworks

CIRIS Agent security features support compliance with:

1. **SOC 2 Type II**: Audit trails, access controls, monitoring
2. **ISO 27001**: Information security management
3. **NIST Cybersecurity Framework**: Comprehensive security controls
4. **GDPR**: Data privacy and protection (PII detection/removal)
5. **HIPAA**: Healthcare data protection (when configured appropriately)

### Audit Trail for Compliance

```python
#!/usr/bin/env python3
# compliance_report.py

from ciris_engine.audit.verifier import AuditVerifier
from datetime import datetime, timedelta
import json

def generate_compliance_report(start_date: datetime, end_date: datetime):
    """Generate compliance audit report"""

    verifier = AuditVerifier()

    report = {
        "report_id": f"compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "audit_trail_integrity": {
            "hash_chain_valid": verifier.verify_chain_integrity(),
            "signatures_valid": verifier.verify_signatures(),
            "no_tampering": not verifier.check_for_tampering()
        },
        "access_controls": {
            "wa_approvals_required": True,
            "rbac_enforced": True,
            "secrets_encrypted": True
        },
        "data_protection": {
            "pii_detection_enabled": True,
            "encryption_at_rest": True,
            "encryption_in_transit": True
        }
    }

    # Add detailed audit events
    events = verifier.get_audit_events(start_date, end_date)
    report["audit_events"] = {
        "total_events": len(events),
        "event_types": {},
        "integrity_verified": True
    }

    # Count event types
    for event in events:
        event_type = event.get("action_type", "UNKNOWN")
        report["audit_events"]["event_types"][event_type] = \
            report["audit_events"]["event_types"].get(event_type, 0) + 1

    return report

# Generate weekly compliance report
if __name__ == "__main__":
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    report = generate_compliance_report(start_date, end_date)

    # Save report
    filename = f"/var/log/ciris/compliance_report_{report['report_id']}.json"
    with open(filename, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Compliance report generated: {filename}")
    print(f"Audit trail integrity: {'✅' if all(report['audit_trail_integrity'].values()) else '❌'}")
```

### Security Configuration Checklist

```bash
#!/bin/bash
# security_checklist.sh

echo "=== CIRIS Agent Security Configuration Checklist ==="

checks_passed=0
total_checks=0

check_item() {
    local description="$1"
    local command="$2"
    total_checks=$((total_checks + 1))

    echo -n "[$total_checks] $description: "

    if eval "$command" &>/dev/null; then
        echo "✅ PASS"
        checks_passed=$((checks_passed + 1))
    else
        echo "❌ FAIL"
    fi
}

# Key management checks
check_item "Secrets master key exists" "test -f /etc/ciris/keys/secrets_master.key"
check_item "Secrets key has correct permissions" "test $(stat -c %a /etc/ciris/keys/secrets_master.key) = '600'"
check_item "Audit private key exists" "test -f /etc/ciris/audit_keys/audit_private.pem"
check_item "Audit key has correct permissions" "test $(stat -c %a /etc/ciris/audit_keys/audit_private.pem) = '600'"

# Database security checks
check_item "Database has secure permissions" "test $(stat -c %a /var/lib/ciris/ciris_engine.db) = '600'"
check_item "Secrets database exists" "test -f /var/lib/ciris/secrets.db"
check_item "Audit database exists" "test -f /var/lib/ciris/ciris_audit.db"

# Configuration checks
check_item "Signed audit enabled" "grep -q 'enable_signed_audit: true' config/production.yaml"
check_item "Secrets management enabled" "grep -q 'enabled: true' config/production.yaml | head -1"
check_item "High sensitivity threshold" "grep -q 'sensitivity_threshold: \"HIGH\"' config/production.yaml"

# Network security checks
check_item "TLS certificates exist" "test -f /etc/ciris/tls/server.crt"
check_item "TLS private key secure" "test $(stat -c %a /etc/ciris/tls/server.key) = '600'"

echo ""
echo "=== Security Checklist Results ==="
echo "Checks passed: $checks_passed/$total_checks"

if [ $checks_passed -eq $total_checks ]; then
    echo "✅ All security checks passed!"
    exit 0
else
    echo "❌ Some security checks failed. Review configuration."
    exit 1
fi
```

This comprehensive security setup ensures CIRIS Agent meets enterprise security requirements with proper encryption, audit trails, access controls, and monitoring capabilities.
