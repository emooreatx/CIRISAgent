"""
LLM service endpoints for CIRIS API v1.

Exposes the agent's language capabilities and resource usage.
Note: Direct generation is not exposed - use agent messages instead.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field

from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.schemas.runtime.resources import ResourceUsage
from ciris_engine.api.dependencies.auth import require_observer, AuthContext

router = APIRouter(prefix="/llm", tags=["llm"])

# Response schemas

class LLMUsage(BaseModel):
    """LLM usage statistics."""
    total_tokens: int = Field(..., description="Total tokens consumed")
    input_tokens: int = Field(..., description="Input tokens used")
    output_tokens: int = Field(..., description="Output tokens generated")
    total_cost_cents: float = Field(..., description="Total cost in cents")
    carbon_grams: float = Field(..., description="Carbon footprint in grams")
    period_start: datetime = Field(..., description="Usage period start")
    period_end: datetime = Field(..., description="Usage period end")

class ModelInfo(BaseModel):
    """Information about an available model."""
    model_name: str = Field(..., description="Model identifier")
    provider: str = Field(..., description="Model provider (OpenAI, Anthropic, etc)")
    context_window: int = Field(..., description="Maximum context size")
    cost_per_million_input: float = Field(..., description="Cost per million input tokens")
    cost_per_million_output: float = Field(..., description="Cost per million output tokens")
    capabilities: List[str] = Field(..., description="Model capabilities")
    is_active: bool = Field(..., description="Whether model is currently active")

class ModelList(BaseModel):
    """List of available models."""
    models: List[ModelInfo] = Field(..., description="Available language models")
    active_model: str = Field(..., description="Currently active model")

class LLMCapabilities(BaseModel):
    """LLM service capabilities."""
    structured_generation: bool = Field(True, description="Supports structured output")
    function_calling: bool = Field(True, description="Supports function/tool calling")
    streaming: bool = Field(True, description="Supports streaming responses")
    max_tokens: int = Field(..., description="Maximum tokens per request")
    supported_languages: List[str] = Field(..., description="Supported languages")
    special_features: List[str] = Field(..., description="Special model features")

# Endpoints

@router.get("/usage", response_model=SuccessResponse[LLMUsage])
async def get_llm_usage(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Token usage and costs.
    
    Get LLM token consumption and associated costs.
    """
    llm_service = getattr(request.app.state, 'llm_service', None)
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    try:
        # Get usage from LLM service
        if hasattr(llm_service, 'get_usage_stats'):
            stats = await llm_service.get_usage_stats()
            
            usage = LLMUsage(
                total_tokens=stats.get('total_tokens', 0),
                input_tokens=stats.get('input_tokens', 0),
                output_tokens=stats.get('output_tokens', 0),
                total_cost_cents=stats.get('cost_cents', 0.0),
                carbon_grams=stats.get('carbon_grams', 0.0),
                period_start=stats.get('period_start', datetime.now(timezone.utc)),
                period_end=stats.get('period_end', datetime.now(timezone.utc))
            )
        else:
            # Fallback: try to get from recent generations
            usage = LLMUsage(
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                total_cost_cents=0.0,
                carbon_grams=0.0,
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc)
            )
        
        return SuccessResponse(data=usage)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models", response_model=SuccessResponse[ModelList])
async def get_available_models(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Available models.
    
    List language models available to the agent.
    """
    llm_service = getattr(request.app.state, 'llm_service', None)
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    try:
        # Get current model
        active_model = "gpt-4o-mini"  # Default
        if hasattr(llm_service, 'model_name'):
            active_model = llm_service.model_name
        elif hasattr(llm_service, 'get_model_name'):
            active_model = await llm_service.get_model_name()
        
        # Define available models
        models = [
            ModelInfo(
                model_name="gpt-4o-mini",
                provider="OpenAI",
                context_window=128000,
                cost_per_million_input=0.15,
                cost_per_million_output=0.60,
                capabilities=["chat", "function_calling", "structured_output"],
                is_active=active_model == "gpt-4o-mini"
            ),
            ModelInfo(
                model_name="meta-llama/Llama-3-8B-Instruct",
                provider="Groq",
                context_window=8192,
                cost_per_million_input=0.10,
                cost_per_million_output=0.10,
                capabilities=["chat", "fast_inference"],
                is_active="llama" in active_model.lower()
            ),
            ModelInfo(
                model_name="mock-llm",
                provider="Internal",
                context_window=4096,
                cost_per_million_input=0.0,
                cost_per_million_output=0.0,
                capabilities=["testing", "offline"],
                is_active=active_model == "mock-llm"
            )
        ]
        
        model_list = ModelList(
            models=models,
            active_model=active_model
        )
        
        return SuccessResponse(data=model_list)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/capabilities", response_model=SuccessResponse[LLMCapabilities])
async def get_llm_capabilities(
    request: Request,
    auth: AuthContext = Depends(require_observer)
):
    """
    Model capabilities.
    
    Get capabilities of the current language model.
    """
    llm_service = getattr(request.app.state, 'llm_service', None)
    if not llm_service:
        raise HTTPException(status_code=503, detail="LLM service not available")
    
    try:
        # Get model-specific capabilities
        max_tokens = 4096  # Default
        if hasattr(llm_service, 'max_tokens'):
            max_tokens = llm_service.max_tokens
        elif hasattr(llm_service, 'get_max_tokens'):
            max_tokens = await llm_service.get_max_tokens()
        
        capabilities = LLMCapabilities(
            structured_generation=True,
            function_calling=True,
            streaming=True,
            max_tokens=max_tokens,
            supported_languages=[
                "English", "Spanish", "French", "German", 
                "Italian", "Portuguese", "Dutch", "Russian",
                "Chinese", "Japanese", "Korean"
            ],
            special_features=[
                "pydantic_schemas",
                "json_mode",
                "tool_calling",
                "chain_of_thought",
                "few_shot_learning"
            ]
        )
        
        return SuccessResponse(data=capabilities)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))