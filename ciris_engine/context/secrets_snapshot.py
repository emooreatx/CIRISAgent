from typing import Dict, Any, List
import logging
from ciris_engine.secrets.service import SecretsService
from ciris_engine.schemas.secrets_schemas_v1 import SecretReference

logger = logging.getLogger(__name__)

async def build_secrets_snapshot(secrets_service: SecretsService) -> Dict[str, Any]:
    """Build secrets information for SystemSnapshot."""
    try:
        # Get recent secrets (limit to last 10 for context)
        all_secrets = await secrets_service.store.list_all_secrets()
        recent_secrets = sorted(all_secrets, key=lambda s: s.created_at, reverse=True)[:10]

        # Convert to SecretReference objects for the snapshot
        detected_secrets: List[SecretReference] = [
            SecretReference(
                uuid=secret.secret_uuid,
                description=secret.description,
                context_hint=secret.context_hint,
                sensitivity=secret.sensitivity_level,
                detected_pattern=getattr(secret, 'detected_pattern', 'unknown'),
                auto_decapsulate_actions=secret.auto_decapsulate_for_actions,
                created_at=secret.created_at,
                last_accessed=secret.last_accessed,
            )
            for secret in recent_secrets
        ]

        # Get filter version
        filter_version = secrets_service.filter.config.version

        # Get total count
        total_secrets = len(all_secrets)

        return {
            "detected_secrets": detected_secrets,
            "secrets_filter_version": filter_version,
            "total_secrets_stored": total_secrets,
        }

    except Exception as e:  # pragma: no cover - defensive
        logger.error(f"Error building secrets snapshot: {e}")
        return {
            "detected_secrets": [],
            "secrets_filter_version": 0,
            "total_secrets_stored": 0,
        }
