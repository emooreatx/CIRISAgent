"""Endpoint security definitions."""
from typing import Dict, List
from pydantic import BaseModel


class EndpointSecurity(BaseModel):
    """Security requirements for API endpoints."""
    
    # Endpoint to required scopes mapping
    ENDPOINT_SCOPES: Dict[str, List[str]] = {
        # Public endpoints
        "GET /v1/health": [],
        "POST /v1/auth/login": [],
        "GET /v1/auth/oauth/*/start": [],
        "GET /v1/auth/oauth/*/callback": [],
        
        # Observer endpoints
        "GET /v1/chat": ["read:any"],
        "GET /v1/audit": ["read:any"],
        "POST /v1/chat": ["write:message"],
        
        # Authority endpoints
        "POST /v1/task": ["write:task"],
        "POST /v1/guidance": ["write:guidance"],
        "POST /v1/wa/mint": ["wa:mint"],
        "POST /v1/wa/*/promote": ["wa:mint"],
        "POST /v1/wa/*/revoke": ["wa:revoke"],
        
        # Root only endpoints
        "POST /v1/system/kill": ["system:control"],
        "PATCH /v1/identity": ["identity:patch"],
        "POST /v1/wa/*/admin": ["wa:admin"]
    }
    
    @classmethod
    def get_required_scopes(cls, method: str, path: str) -> List[str]:
        """Get required scopes for endpoint."""
        endpoint = f"{method} {path}"
        
        # Check exact match
        if endpoint in cls.ENDPOINT_SCOPES:
            return cls.ENDPOINT_SCOPES[endpoint]
        
        # Check wildcard patterns
        for pattern, scopes in cls.ENDPOINT_SCOPES.items():
            if "*" in pattern:
                pattern_regex = pattern.replace("*", "[^/]+")
                import re
                if re.match(f"^{pattern_regex}$", endpoint):
                    return scopes
        
        # Default to requiring authentication but no specific scope
        return ["authenticated"]