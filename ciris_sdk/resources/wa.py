"""Wise Authority resource for the CIRIS SDK."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from ..transport import Transport


class WiseAuthorityResource:
    """Client for interacting with Wise Authority endpoints."""
    
    def __init__(self, transport: Transport):
        self._transport = transport
    
    async def get_deferrals(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get list of deferrals.
        
        Args:
            status: Filter by status (pending, resolved, expired)
            limit: Maximum number of deferrals to return
            offset: Number of deferrals to skip
            
        Returns:
            Dict containing deferrals list and pagination info
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        if status:
            params["status"] = status
            
        resp = await self._transport.request("GET", "/v1/wa/deferrals", params=params)
        return resp.json()
    
    async def resolve_deferral(
        self,
        deferral_id: str,
        resolution: str,
        guidance: Optional[str] = None,
        reasoning: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resolve a deferral with integrated guidance.
        
        Args:
            deferral_id: The ID of the deferral to resolve
            resolution: The resolution decision (e.g., "approved", "rejected", "modified")
            guidance: Optional guidance for the agent
            reasoning: Optional explanation of the decision
            
        Returns:
            Dict containing the resolved deferral details
        """
        payload = {
            "resolution": resolution
        }
        if guidance:
            payload["guidance"] = guidance
        if reasoning:
            payload["reasoning"] = reasoning
            
        resp = await self._transport.request(
            "POST", 
            f"/v1/wa/deferrals/{deferral_id}/resolve",
            json=payload
        )
        return resp.json()
    
    async def get_permissions(
        self,
        resource_type: Optional[str] = None,
        permission_type: Optional[str] = None,
        active_only: bool = True
    ) -> Dict[str, Any]:
        """Get current permissions.
        
        Args:
            resource_type: Filter by resource type
            permission_type: Filter by permission type
            active_only: Only return active permissions
            
        Returns:
            Dict containing permissions list
        """
        params = {
            "active_only": active_only
        }
        if resource_type:
            params["resource_type"] = resource_type
        if permission_type:
            params["permission_type"] = permission_type
            
        resp = await self._transport.request("GET", "/v1/wa/permissions", params=params)
        return resp.json()
    
    # Helper methods for common operations
    
    async def get_pending_deferrals(self) -> List[Dict[str, Any]]:
        """Get all pending deferrals."""
        result = await self.get_deferrals(status="pending")
        return result.get("deferrals", [])
    
    async def approve_deferral(
        self,
        deferral_id: str,
        guidance: Optional[str] = None
    ) -> Dict[str, Any]:
        """Approve a deferral with optional guidance."""
        return await self.resolve_deferral(
            deferral_id=deferral_id,
            resolution="approved",
            guidance=guidance
        )
    
    async def reject_deferral(
        self,
        deferral_id: str,
        reasoning: str
    ) -> Dict[str, Any]:
        """Reject a deferral with reasoning."""
        return await self.resolve_deferral(
            deferral_id=deferral_id,
            resolution="rejected",
            reasoning=reasoning
        )
    
    async def modify_deferral(
        self,
        deferral_id: str,
        guidance: str,
        reasoning: Optional[str] = None
    ) -> Dict[str, Any]:
        """Modify a deferral with new guidance."""
        return await self.resolve_deferral(
            deferral_id=deferral_id,
            resolution="modified",
            guidance=guidance,
            reasoning=reasoning
        )