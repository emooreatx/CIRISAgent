"""GraphQL operation schemas for type safety."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class GraphQLVariable(BaseModel):
    """Base model for GraphQL variables."""
    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class GraphQLQuery(BaseModel):
    """GraphQL query request."""
    query: str = Field(description="GraphQL query string")
    variables: GraphQLVariable = Field(default_factory=GraphQLVariable, description="Query variables")
    operation_name: Optional[str] = Field(default=None, description="Operation name for multi-operation documents")


class GraphQLUser(BaseModel):
    """User data from GraphQL response."""
    name: str = Field(description="User name")
    nick: Optional[str] = Field(default=None, description="User nickname")
    channel: Optional[str] = Field(default=None, description="User's primary channel")


class UserQueryVariables(GraphQLVariable):
    """Variables for user query."""
    names: List[str] = Field(description="List of user names to query")


class UserQueryResponse(BaseModel):
    """Response from user query."""
    users: List[GraphQLUser] = Field(default_factory=list, description="List of user data")


class GraphQLResponse(BaseModel):
    """Generic GraphQL response wrapper."""
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    errors: Optional[List[Dict[str, Any]]] = Field(default=None, description="GraphQL errors")
    extensions: Optional[Dict[str, Any]] = Field(default=None, description="Response extensions")


class UserProfile(BaseModel):
    """Enriched user profile data."""
    nick: Optional[str] = Field(default=None, description="User nickname")
    channel: Optional[str] = Field(default=None, description="User's primary channel")
    # Additional fields from memory service
    attributes: Optional[Dict[str, Any]] = Field(default=None, description="Additional user attributes")


class EnrichedContext(BaseModel):
    """Enriched context data."""
    user_profiles: Dict[str, UserProfile] = Field(default_factory=dict, description="User profiles by name")
    identity_context: Optional[str] = Field(default=None, description="Identity context block")