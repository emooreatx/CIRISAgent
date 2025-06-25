"""
Base class and utilities for typed graph nodes.

This module provides the foundation for type-safe graph nodes that can be
stored generically while maintaining full type information.
"""
from typing import Dict, Any, Type, TypeVar, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope

T = TypeVar('T', bound='TypedGraphNode')

class TypedGraphNode(GraphNode, ABC):
    """
    Abstract base class for all typed graph nodes.
    
    Subclasses must implement to_graph_node() and from_graph_node()
    to handle serialization to/from generic GraphNode storage.
    """
    
    @abstractmethod
    def to_graph_node(self) -> GraphNode:
        """
        Convert this typed node to a generic GraphNode for storage.
        
        Should only include extra fields (beyond GraphNode base fields)
        in the attributes dict.
        """
        pass
    
    @classmethod
    @abstractmethod
    def from_graph_node(cls: Type[T], node: GraphNode) -> T:
        """
        Reconstruct a typed node from a generic GraphNode.
        
        Should handle deserialization of extra fields from attributes.
        """
        pass
    
    def _serialize_extra_fields(self, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Helper to serialize only the extra fields (not in GraphNode base).
        
        Args:
            exclude_fields: Additional fields to exclude beyond base fields
            
        Returns:
            Dict of extra fields suitable for GraphNode attributes
        """
        # Base GraphNode fields to always exclude
        base_fields = {
            'id', 'type', 'scope', 'attributes', 
            'version', 'updated_by', 'updated_at'
        }
        
        # Add any additional exclusions
        if exclude_fields:
            base_fields.update(exclude_fields)
        
        # Get all fields from this model
        extra_data = {}
        for field_name, field_value in self.model_dump().items():
            if field_name not in base_fields and field_value is not None:
                # Handle special types
                if isinstance(field_value, datetime):
                    extra_data[field_name] = field_value.isoformat()
                elif isinstance(field_value, BaseModel):
                    extra_data[field_name] = field_value.model_dump()
                else:
                    extra_data[field_name] = field_value
        
        # Add type hint for deserialization
        extra_data['_node_class'] = self.__class__.__name__
        
        return extra_data
    
    @classmethod
    def _deserialize_datetime(cls, value: Any) -> Optional[datetime]:
        """Helper to deserialize datetime from string."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError(f"Cannot deserialize datetime from {type(value)}")

class NodeTypeRegistry:
    """
    Registry for typed node classes.
    
    Allows looking up node classes by type string for deserialization.
    """
    
    _registry: Dict[str, Type[TypedGraphNode]] = {}
    
    @classmethod
    def register(cls, node_type: str, node_class: Type[TypedGraphNode]) -> None:
        """Register a node class for a type string."""
        if node_type in cls._registry:
            raise ValueError(f"Node type {node_type} already registered")
        
        # Validate the class has required methods
        if not hasattr(node_class, 'to_graph_node'):
            raise ValueError(f"{node_class.__name__} must implement to_graph_node()")
        if not hasattr(node_class, 'from_graph_node'):
            raise ValueError(f"{node_class.__name__} must implement from_graph_node()")
        
        cls._registry[node_type] = node_class
    
    @classmethod
    def get(cls, node_type: str) -> Optional[Type[TypedGraphNode]]:
        """Get a node class by type string."""
        return cls._registry.get(node_type)
    
    @classmethod
    def deserialize(cls, node: GraphNode) -> TypedGraphNode:
        """
        Deserialize a GraphNode to its typed variant if registered.
        
        Falls back to returning the GraphNode if type not registered.
        """
        node_class = cls._registry.get(node.type)
        if node_class and hasattr(node.attributes, 'get'):
            # Check if this was serialized from a typed node
            class_name = node.attributes.get('_node_class')
            if class_name:
                # Try to deserialize to typed node
                try:
                    return node_class.from_graph_node(node)
                except Exception:
                    # Fall back to generic if deserialization fails
                    pass
        
        return node

def register_node_type(node_type: str):
    """
    Decorator to automatically register a node type.
    
    Usage:
        @register_node_type("CONFIG")
        class ConfigNode(TypedGraphNode):
            ...
    """
    def decorator(cls: Type[TypedGraphNode]) -> Type[TypedGraphNode]:
        NodeTypeRegistry.register(node_type, cls)
        return cls
    
    return decorator