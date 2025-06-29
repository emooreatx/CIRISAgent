"""
Incident management endpoints for CIRIS API v1.

Track and manage system incidents and problems.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import List, Optional

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.api.dependencies.auth import require_observer, require_admin, AuthContext

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.get("/", response_model=SuccessResponse[List[dict]])
async def get_incidents(
    request: Request,
    auth: AuthContext = Depends(require_observer),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum incidents to return")
):
    """
    Get recent incidents.

    Returns list of recent incidents with optional filtering.
    """
    incident_service = getattr(request.app.state, 'incident_management', None)
    if not incident_service:
        # Return empty list if service not available
        return SuccessResponse(data=[])

    try:
        # Query incidents from service
        incidents = await incident_service.query_incidents(
            severity=severity,
            status=status,
            limit=limit
        )

        # Convert to response format
        incident_data = []
        for incident in incidents:
            incident_data.append({
                "incident_id": incident.incident_id,
                "severity": incident.severity,
                "status": incident.status,
                "description": incident.description,
                "created_at": incident.created_at.isoformat() if hasattr(incident.created_at, 'isoformat') else str(incident.created_at),
                "updated_at": incident.updated_at.isoformat() if hasattr(incident.updated_at, 'isoformat') else str(incident.updated_at),
                "resolution": getattr(incident, 'resolution', None)
            })

        return SuccessResponse(data=incident_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{incident_id}", response_model=SuccessResponse[dict])
async def get_incident(
    request: Request,
    incident_id: str,
    auth: AuthContext = Depends(require_observer)
):
    """
    Get specific incident.

    Returns detailed information about a specific incident.
    """
    incident_service = getattr(request.app.state, 'incident_management', None)
    if not incident_service:
        raise HTTPException(status_code=503, detail="Incident service not available")

    try:
        incident = await incident_service.get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

        return SuccessResponse(data={
            "incident_id": incident.incident_id,
            "severity": incident.severity,
            "status": incident.status,
            "description": incident.description,
            "created_at": incident.created_at.isoformat() if hasattr(incident.created_at, 'isoformat') else str(incident.created_at),
            "updated_at": incident.updated_at.isoformat() if hasattr(incident.updated_at, 'isoformat') else str(incident.updated_at),
            "resolution": getattr(incident, 'resolution', None),
            "insights": getattr(incident, 'insights', [])
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{incident_id}/resolve", response_model=SuccessResponse[dict])
async def resolve_incident(
    request: Request,
    incident_id: str,
    resolution: dict,
    auth: AuthContext = Depends(require_admin)
):
    """
    Resolve an incident.

    Mark an incident as resolved with resolution details. Requires ADMIN role.
    """
    incident_service = getattr(request.app.state, 'incident_management', None)
    if not incident_service:
        raise HTTPException(status_code=503, detail="Incident service not available")

    try:
        # Resolve the incident
        updated_incident = await incident_service.resolve_incident(
            incident_id,
            resolution.get('description', ''),
            resolution.get('root_cause', ''),
            resolution.get('preventive_measures', [])
        )

        if not updated_incident:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")

        return SuccessResponse(data={
            "incident_id": updated_incident.incident_id,
            "status": "resolved",
            "resolution": resolution
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
