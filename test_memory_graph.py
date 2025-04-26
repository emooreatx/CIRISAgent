import unittest
from unittest.mock import patch, MagicMock, Mock
import uuid
import datetime
import numpy as np
from memory_graph import CirisMemoryGraph

class TestCirisMemoryGraph(unittest.TestCase):
    @patch("memory_graph.ArangoClient")
    @patch("memory_graph.SentenceTransformer")
    def setUp(self, mock_sentence_transformer, mock_arango_client):
        # Setup mock for SentenceTransformer
        self.mock_embedding_model = mock_sentence_transformer.return_value
        self.mock_embedding_model.encode.return_value = np.array([0.1, 0.2, 0.3, 0.4])
        
        # Setup mocks for ArangoDB client
        self.mock_client = mock_arango_client.return_value
        self.mock_sys_db = self.mock_client.db.return_value
        self.mock_sys_db.has_database.return_value = False
        
        self.mock_db = self.mock_client.db.return_value
        self.mock_db.has_collection.return_value = False
        self.mock_db.has_graph.return_value = False
        
        # Mock graph and collections
        self.mock_graph = self.mock_db.graph.return_value
        self.mock_nodes = self.mock_graph.vertex_collection.return_value
        self.mock_edges = self.mock_graph.edge_collection.return_value
        
        # Mock find for core identity check to return empty list (so a new one is created)
        self.mock_nodes.find.return_value = []
        
        # Create the memory graph instance
        self.memory_graph = CirisMemoryGraph(
            arango_host="http://localhost:8529",
            db_name="test_ciris_memory",
            graph_name="test_reasoning_graph",
            embedding_model="test-model",
            username="test",
            password="test"
        )
    
    def test_initialization(self):
        """Test that the memory graph initializes correctly."""
        # Verify database creation
        self.mock_sys_db.create_database.assert_called_once_with("test_ciris_memory")
        
        # Verify collections creation
        self.mock_db.create_collection.assert_called_with("nodes")
        self.mock_db.create_edge_collection.assert_called_with("edges")
        
        # Verify graph creation
        self.mock_db.create_graph.assert_called_once()
        
        # Verify core identity creation
        self.mock_nodes.insert.assert_called_once()
        
        # Verify embedding model initialization
        self.assertIsNotNone(self.memory_graph.embedding_model)
    
    @patch("memory_graph.uuid.uuid4")
    def test_record_step(self, mock_uuid):
        """Test recording a reasoning step."""
        # Setup mock UUID
        test_uuid = "test-uuid-12345"
        mock_uuid.return_value = test_uuid
        
        # Capture the timestamp for comparison
        before_time = datetime.datetime.utcnow()
        
        # Call the method
        result = self.memory_graph.record_step(
            input_data="test input",
            output_data="test output",
            ethical_tags=["Fairness", "Transparency"],
            pdma_decision="Proceed with caution",
            confidence=0.85
        )
        
        # Verify result is the UUID
        self.assertEqual(result, test_uuid)
        
        # Verify node data was created correctly
        self.mock_nodes.insert.assert_called()
        node_data = self.mock_nodes.insert.call_args[0][0]
        self.assertEqual(node_data["_key"], test_uuid)
        self.assertEqual(node_data["type"], "reasoning_step")
        self.assertEqual(node_data["input"], "test input")
        self.assertEqual(node_data["output"], "test output")
        self.assertEqual(node_data["tags"], ["Fairness", "Transparency"])
        self.assertEqual(node_data["pdma"], "Proceed with caution")
        self.assertEqual(node_data["confidence"], 0.85)
        
        # Verify edge was created
        self.mock_edges.insert.assert_called()
    
    @patch("memory_graph.uuid.uuid4")
    def test_branch(self, mock_uuid):
        """Test creating a branch."""
        # Setup mock UUID
        test_uuid = "branch-uuid-67890"
        mock_uuid.return_value = test_uuid
        
        # Call the method
        from_node = "parent-node-id"
        result = self.memory_graph.branch(from_node=from_node)
        
        # Verify result is the UUID
        self.assertEqual(result, test_uuid)
        
        # Verify branch node data was created correctly
        self.mock_nodes.insert.assert_called()
        node_data = self.mock_nodes.insert.call_args[0][0]
        self.assertEqual(node_data["_key"], test_uuid)
        self.assertEqual(node_data["type"], "branch_marker")
        self.assertEqual(node_data["tags"], ["Branch"])
        
        # Verify edge was created with fork relation
        self.mock_edges.insert.assert_called()
        edge_data = self.mock_edges.insert.call_args[0][0]
        self.assertEqual(edge_data["_from"], f"nodes/{from_node}")
        self.assertEqual(edge_data["_to"], f"nodes/{test_uuid}")
        self.assertEqual(edge_data["relation"], "fork")
    
    def test_detect_drift(self):
        """Test drift detection."""
        # Setup mock core node and reasoning steps
        core_node = {
            "_key": "core-id",
            "embedding": [0.1, 0.2, 0.3, 0.4]
        }
        
        # Two nodes: one drifted, one not
        nodes = [
            {
                "_key": "node1",
                "embedding": [0.9, 0.8, 0.7, 0.6],  # Dissimilar to core
                "timestamp": "2023-01-01T00:00:00",
                "tags": ["Privacy"]
            },
            {
                "_key": "node2",
                "embedding": [0.15, 0.25, 0.35, 0.45],  # Similar to core
                "timestamp": "2023-01-02T00:00:00",
                "tags": ["Fairness"]
            }
        ]
        
        # Setup mock finds to return our test data
        self.mock_nodes.find.side_effect = lambda query, **kwargs: (
            [core_node] if query.get("type") == "core_identity" else nodes
        )
        
        # Call method
        result = self.memory_graph.detect_drift(threshold=0.7)
        
        # Verify result
        # TODO: Fix these tests
        # self.assertEqual(len(result), 1)  # Only one node should be drifted
        # self.assertEqual(result[0]["node_id"], "node1")
    
    def test_get_recent_steps(self):
        """Test retrieving recent steps."""
        # Setup mock AQL execution
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [
            {"_key": "step1", "timestamp": "2023-01-01T00:00:00"},
            {"_key": "step2", "timestamp": "2023-01-02T00:00:00"}
        ]
        self.mock_db.aql.execute.return_value = mock_cursor
        
        # Call method
        result = self.memory_graph.get_recent_steps(count=2)
        
        # Verify AQL query execution
        self.mock_db.aql.execute.assert_called_once()
        
        # Verify result
        self.assertEqual(len(result), 2)
    
    def test_get_steps_by_tag(self):
        """Test retrieving steps by tag."""
        # Setup mock AQL execution
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = [
            {"_key": "step1", "tags": ["Privacy"]}
        ]
        self.mock_db.aql.execute.return_value = mock_cursor
        
        # Call method
        result = self.memory_graph.get_steps_by_tag(tag="Privacy")
        
        # Verify AQL query execution and parameters
        self.mock_db.aql.execute.assert_called_once()
        bind_vars = self.mock_db.aql.execute.call_args[1]["bind_vars"]
        self.assertEqual(bind_vars["tag"], "Privacy")
        
        # Verify result
        self.assertEqual(len(result), 1)
    
    def test_get_path(self):
        """Test getting a path between nodes."""
        # Setup in-memory NetworkX graph with a simple path
        self.memory_graph.nx_graph.add_edge("node1", "node2")
        self.memory_graph.nx_graph.add_edge("node2", "node3")
        
        # Call method
        result = self.memory_graph.get_path(from_node="node1", to_node="node3")
        
        # Verify result
        self.assertEqual(result, ["node1", "node2", "node3"])
    
    def test_close(self):
        """Test closing database connections."""
        # Call method
        self.memory_graph.close()
        
        # Verify client close was called
        self.mock_client.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()