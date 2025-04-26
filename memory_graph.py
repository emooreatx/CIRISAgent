import uuid
import datetime
import networkx as nx
import numpy as np
import os
from typing import List, Dict, Any, Optional, Union, Tuple
from arango import ArangoClient
from adbnx_adapter import ADBNX_Adapter, ADBNX_Controller
from sentence_transformers import SentenceTransformer

class CirisMemoryGraph:
    """
    Enhanced CIRIS memory ledger using ArangoDB for persistence and advanced
    embedding-based drift detection.
    """
    
    def __init__(self, 
                 arango_host: str = "http://localhost:8529", 
                 db_name: str = "ciris_memory",
                 graph_name: str = "reasoning_graph",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 username: str = os.environ.get("ARANGO_USERNAME", "root"),
                 password: str = os.environ.get("ARANGO_PASSWORD", "cirispassword")):
        """
        Initialize the memory graph with ArangoDB connection.
        
        Args:
            arango_host: URL for ArangoDB server
            db_name: Database name to use
            graph_name: Name of the graph in ArangoDB
            embedding_model: SentenceTransformer model to use for embeddings
            username: ArangoDB username
            password: ArangoDB password
        """
        # Connect to ArangoDB
        self.client = ArangoClient(hosts=arango_host)
        self.sys_db = self.client.db("_system", username=username, password=password)
        
        # Create database if it doesn't exist
        if not self.sys_db.has_database(db_name):
            self.sys_db.create_database(db_name)
        
        # Connect to the database
        self.db = self.client.db(db_name, username=username, password=password)
        
        # Create collections if they don't exist
        if not self.db.has_collection("nodes"):
            self.db.create_collection("nodes")
        if not self.db.has_collection("edges"):
            # Fix: create a regular collection with edge=True parameter
            self.db.create_collection("edges", edge=True)
            
        # Create graph if it doesn't exist
        if not self.db.has_graph(graph_name):
            self.db.create_graph(
                graph_name,
                edge_definitions=[
                    {
                        "edge_collection": "edges",
                        "from_vertex_collections": ["nodes"],
                        "to_vertex_collections": ["nodes"]
                    }
                ]
            )
        
        self.graph = self.db.graph(graph_name)
        self.nodes = self.graph.vertex_collection("nodes")
        self.edges = self.graph.edge_collection("edges")
        
        # Initialize embedding model for semantic similarity
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # In-memory graph for visualization and quick operations
        self.nx_graph = nx.DiGraph()
        
        # Check if we have a core identity node, create if not
        core_nodes = list(self.nodes.find({"type": "core_identity"}, limit=1))
        if not core_nodes:
            self._create_core_identity()
        else:
            self.latest = core_nodes[0]["_key"]
            # Load existing graph into NetworkX
            self._load_graph_to_nx()

    def _create_core_identity(self) -> None:
        """Create the core identity node as the root of the graph."""
        root_id = str(uuid.uuid4())
        core_tags = ["Integrity", "Continuity"]
        
        # Create in ArangoDB
        node_data = {
            "_key": root_id,
            "type": "core_identity",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "tags": core_tags,
            "embedding": self._get_embedding(core_tags).tolist()
        }
        self.nodes.insert(node_data)
        
        # Add to NetworkX graph
        self.nx_graph.add_node(root_id, **node_data)
        self.latest = root_id
        
    def _get_embedding(self, text_data: Union[str, List[str]]) -> np.ndarray:
        """Generate embeddings for text or lists of text."""
        if isinstance(text_data, list):
            text_data = " ".join(text_data)
        return self.embedding_model.encode(text_data)
    
    def _load_graph_to_nx(self) -> None:
        """Load the complete graph from ArangoDB into NetworkX."""
        # Clear existing data
        self.nx_graph.clear()
        
        # Load all nodes
        for node in self.nodes.all():
            self.nx_graph.add_node(node["_key"], **node)
            
        # Load all edges
        for edge in self.edges.all():
            self.nx_graph.add_edge(
                edge["_from"].split("/")[1], 
                edge["_to"].split("/")[1],
                relation=edge["relation"]
            )

    def record_step(self, *, 
                   input_data: str,
                   output_data: str,
                   ethical_tags: List[str],
                   pdma_decision: str,
                   confidence: float = 1.0,
                   parent: str = None) -> str:
        """
        Add a reasoning step node and link it to its parent.
        
        Args:
            input_data: The input prompt or data
            output_data: The output or response
            ethical_tags: List of ethical considerations
            pdma_decision: Decision under the PDMA framework
            confidence: Confidence score (0.0-1.0)
            parent: Parent node ID (defaults to latest node)
            
        Returns:
            The ID of the created node
        """
        node_id = str(uuid.uuid4())
        # Default parent = latest step
        parent = parent or self.latest
        
        # Create combined text for embedding
        embedding_text = f"{' '.join(ethical_tags)} {pdma_decision}"
        
        # Create node document
        node_data = {
            "_key": node_id,
            "type": "reasoning_step",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "input": input_data,
            "output": output_data,
            "tags": ethical_tags,
            "pdma": pdma_decision,
            "confidence": confidence,
            "embedding": self._get_embedding(embedding_text).tolist()
        }
        
        # Create edge document
        edge_data = {
            "_from": f"nodes/{parent}",
            "_to": f"nodes/{node_id}",
            "relation": "causal",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Insert into ArangoDB
        self.nodes.insert(node_data)
        self.edges.insert(edge_data)
        
        # Update NetworkX graph
        self.nx_graph.add_node(node_id, **node_data)
        self.nx_graph.add_edge(parent, node_id, relation="causal")
        
        self.latest = node_id
        return node_id

    def branch(self, *, from_node: str) -> str:
        """
        Create a fork: start a new line of reasoning from from_node.
        
        Args:
            from_node: The node ID to branch from
            
        Returns:
            ID of the new branch marker node
        """
        fork_id = str(uuid.uuid4())
        
        # Create node
        node_data = {
            "_key": fork_id,
            "type": "branch_marker",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "tags": ["Branch"],
            "embedding": self._get_embedding(["Branch"]).tolist()
        }
        
        # Create edge
        edge_data = {
            "_from": f"nodes/{from_node}",
            "_to": f"nodes/{fork_id}",
            "relation": "fork",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Insert into ArangoDB
        self.nodes.insert(node_data)
        self.edges.insert(edge_data)
        
        # Update NetworkX graph
        self.nx_graph.add_node(fork_id, **node_data)
        self.nx_graph.add_edge(from_node, fork_id, relation="fork")
        
        self.latest = fork_id
        return fork_id

    def detect_drift(self, *, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Enhanced drift detector using semantic embeddings.
        
        Args:
            threshold: Cosine similarity threshold below which nodes are considered drifted
            
        Returns:
            List of drifted nodes with their drift scores
        """
        # Get core identity node
        core_node = list(self.nodes.find({"type": "core_identity"}, limit=1))[0]
        core_embedding = np.array(core_node["embedding"])
        
        drifted = []
        
        # Find reasoning steps and calculate drift
        for node in self.nodes.find({"type": "reasoning_step"}):
            node_embedding = np.array(node["embedding"])
            
            # Compute cosine similarity
            similarity = np.dot(core_embedding, node_embedding) / (
                np.linalg.norm(core_embedding) * np.linalg.norm(node_embedding)
            )
            
            if similarity < threshold:
                drifted.append({
                    "node_id": node["_key"],
                    "similarity": float(similarity),
                    "timestamp": node["timestamp"],
                    "tags": node["tags"]
                })
                
        return sorted(drifted, key=lambda x: x["similarity"])

    def get_path(self, from_node: str, to_node: str) -> List[str]:
        """
        Get the shortest path between two nodes.
        
        Args:
            from_node: Starting node ID
            to_node: Target node ID
            
        Returns:
            List of node IDs representing the path
        """
        try:
            return nx.shortest_path(self.nx_graph, from_node, to_node)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_recent_steps(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get the most recent reasoning steps.
        
        Args:
            count: Number of recent steps to retrieve
            
        Returns:
            List of node data objects
        """
        query = """
        FOR n IN nodes
        FILTER n.type == 'reasoning_step'
        SORT n.timestamp DESC
        LIMIT @count
        RETURN n
        """
        return list(self.db.aql.execute(query, bind_vars={"count": count}))

    def get_steps_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Find all reasoning steps with a specific ethical tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of matching node data objects
        """
        query = """
        FOR n IN nodes
        FILTER n.type == 'reasoning_step' AND @tag IN n.tags
        SORT n.timestamp DESC
        RETURN n
        """
        return list(self.db.aql.execute(query, bind_vars={"tag": tag}))

    def get_steps_since_deferral(self) -> List[Dict[str, Any]]:
        """
        Get all reasoning steps since the last deferral or branch.
        
        Returns:
            List of node data objects
        """
        # Find most recent branch/deferral node
        query = """
        FOR n IN nodes
        FILTER n.type == 'branch_marker'
        SORT n.timestamp DESC
        LIMIT 1
        LET steps = (
            FOR v, e, p IN 1..100 OUTBOUND n._id GRAPH 'reasoning_graph'
            FILTER v.type == 'reasoning_step'
            SORT v.timestamp ASC
            RETURN v
        )
        RETURN steps
        """
        result = list(self.db.aql.execute(query))
        if result and result[0]:
            return result[0]
        return []

    def visualize(self, path: str = "ciris_memory.png"):
        """
        Dump a quick PNG of the current ledger graph (requires Graphviz).
        
        Args:
            path: Output image file path
        """
        try:
            # Generate labels for nodes
            node_labels = {}
            for nid, data in self.nx_graph.nodes(data=True):
                if data.get("type") == "core_identity":
                    node_labels[nid] = "Core Identity"
                elif data.get("type") == "branch_marker":
                    node_labels[nid] = "Branch"
                elif data.get("type") == "reasoning_step":
                    # Truncate long strings
                    pdma = data.get("pdma", "")[:20] + "..." if len(data.get("pdma", "")) > 20 else data.get("pdma", "")
                    node_labels[nid] = f"Step: {pdma}"
            
            # Create visualization with labels
            pos = nx.nx_agraph.graphviz_layout(self.nx_graph, prog="dot")
            plt = __import__('matplotlib.pyplot').pyplot
            plt.figure(figsize=(12, 8))
            
            # Draw nodes by type with different colors
            core_nodes = [n for n, d in self.nx_graph.nodes(data=True) if d.get("type") == "core_identity"]
            branch_nodes = [n for n, d in self.nx_graph.nodes(data=True) if d.get("type") == "branch_marker"]
            step_nodes = [n for n, d in self.nx_graph.nodes(data=True) if d.get("type") == "reasoning_step"]
            
            nx.draw_networkx_nodes(self.nx_graph, pos, nodelist=core_nodes, node_color="gold", node_size=500)
            nx.draw_networkx_nodes(self.nx_graph, pos, nodelist=branch_nodes, node_color="lightblue", node_size=300)
            nx.draw_networkx_nodes(self.nx_graph, pos, nodelist=step_nodes, node_color="lightgreen", node_size=300)
            
            # Draw edges with different styles based on relation
            causal_edges = [(u, v) for u, v, d in self.nx_graph.edges(data=True) if d.get("relation") == "causal"]
            fork_edges = [(u, v) for u, v, d in self.nx_graph.edges(data=True) if d.get("relation") == "fork"]
            
            nx.draw_networkx_edges(self.nx_graph, pos, edgelist=causal_edges, edge_color="gray")
            nx.draw_networkx_edges(self.nx_graph, pos, edgelist=fork_edges, edge_color="blue", style="dashed")
            
            # Add labels
            nx.draw_networkx_labels(self.nx_graph, pos, labels=node_labels, font_size=8)
            
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(path, dpi=300)
            plt.close()
            print(f"Ledger graph written to {path}")
        except Exception as e:
            print("Visualization error (check matplotlib and pygraphviz):", e)

    def export_to_networkx(self) -> nx.DiGraph:
        """
        Export the current graph as a NetworkX DiGraph.
        
        Returns:
            NetworkX directed graph copy
        """
        return self.nx_graph.copy()

    def persist(self) -> None:
        """
        Explicitly save any in-memory changes to ArangoDB.
        This is usually not needed as operations save automatically.
        """
        pass  # All operations directly modify the database

    def close(self) -> None:
        """Close the database connections."""
        if hasattr(self, 'client'):
            self.client.close()
