This adapter provides a simple graph memory service backed by the persistence
SQLite database. It stores graph nodes and edges in the `graph_nodes` and
`graph_edges` tables created by the migration system. Use
`LocalGraphMemoryService` when handlers need a lightweight memory provider.
