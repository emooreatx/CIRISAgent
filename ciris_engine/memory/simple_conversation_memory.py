import logging
from typing import Dict, Optional, List, Any
from collections import deque

logger = logging.getLogger(__name__)

class SimpleConversationMemory:
    def __init__(self, max_history_length: int = 2):
        self.max_history_length = max_history_length
        self.conversation_graphs: Dict[Any, Dict[str, Dict[str, Any]]] = {}
        self.message_order: Dict[Any, deque[str]] = {}
        if self.max_history_length > 0:
            logger.info(f"SimpleConversationMemory initialized with max_history_length: {max_history_length}.")
        else:
            logger.info("SimpleConversationMemory initialized with history disabled (max_history_length <= 0).")

    def _prune_history(self, conversation_id: Any):
        # No need to check self.conversation_graphs or self.message_order for None here,
        # as they are initialized in __init__
        graph = self.conversation_graphs.get(conversation_id)
        order_deque = self.message_order.get(conversation_id)

        if not graph or not order_deque:
            return

        while len(order_deque) > self.max_history_length:
            oldest_msg_id = order_deque.popleft()
            if oldest_msg_id in graph:
                del graph[oldest_msg_id]

    def add_message(self, 
                    conversation_id: Any, 
                    message_id: str, 
                    content: str, 
                    author_name: str, 
                    timestamp: str, 
                    reference_message_id: Optional[str] = None):
        if self.max_history_length <= 0:
            logger.debug(f"Skipping add_message for {conversation_id} because max_history_length <= 0.")
            return

        if conversation_id not in self.conversation_graphs:
            self.conversation_graphs[conversation_id] = {}
        if conversation_id not in self.message_order:
            self.message_order[conversation_id] = deque()

        graph = self.conversation_graphs[conversation_id]
        order_deque = self.message_order[conversation_id]

        graph[message_id] = {
            "content": content,
            "author_name": author_name,
            "timestamp": timestamp,
            "replies": set(),
        }
        order_deque.append(message_id)

        if reference_message_id and reference_message_id in graph:
            graph[reference_message_id].setdefault("replies", set()).add(message_id)
        
        # Prune old messages
        self._prune_history(conversation_id)
        
        logger.debug(f"Added message {message_id} to conversation {conversation_id}. History size: {len(order_deque)}")

    def get_formatted_history(self, conversation_id: Any) -> str:
        if self.max_history_length <= 0:
            logger.debug(f"Skipping get_formatted_history for {conversation_id} because max_history_length <= 0.")
            return ""

        graph = self.conversation_graphs.get(conversation_id)
        order_deque = self.message_order.get(conversation_id)

        if not graph or not order_deque:
            return ""

        history_lines = []
        for msg_id_in_order in order_deque:
            if msg_id_in_order in graph:
                node_data = graph[msg_id_in_order]
                history_lines.append(f"{node_data['author_name']}: {node_data['content']}")
        
        formatted_history = "\n".join(history_lines)
        logger.debug(f"Formatted history for conversation {conversation_id} (last {len(order_deque)} of max {self.max_history_length} messages):\n{formatted_history}")
        return formatted_history

    def is_enabled(self) -> bool:
        return self.max_history_length > 0
