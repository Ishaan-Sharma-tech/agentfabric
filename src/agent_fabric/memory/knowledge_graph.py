import json
from collections import deque
from typing import Dict, Any, List, Optional, Set
from agent_fabric.memory.sqlite_store import get_db_conn, sqlite3

__all__ = ["KnowledgeGraph"]


class KnowledgeGraph:
    """
    Graph memory engine implemented directly on top of SQLite.
    Supports storing nodes and edges, finding neighbors, and computing paths.
    """
    
    def add_node(
        self, 
        node_id: str, 
        node_type: str, 
        name: str, 
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create or update a node in the graph."""
        prop_json = json.dumps(properties or {})
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO graph_nodes (id, type, name, properties)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type = excluded.type,
                name = excluded.name,
                properties = excluded.properties
            """, (node_id, node_type, name, prop_json))

    def add_edge(
        self, 
        source: str, 
        target: str, 
        relationship: str, 
        properties: Optional[Dict[str, Any]] = None
    ) -> None:
        """Create or update a directed edge between two existing nodes."""
        prop_json = json.dumps(properties or {})
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM graph_nodes WHERE id = ?", (source,))
            if not cursor.fetchone():
                raise ValueError(f"Source node '{source}' does not exist.")
            cursor.execute("SELECT 1 FROM graph_nodes WHERE id = ?", (target,))
            if not cursor.fetchone():
                raise ValueError(f"Target node '{target}' does not exist.")

            cursor.execute("""
            INSERT INTO graph_edges (source, target, relationship, properties)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source, target, relationship) DO UPDATE SET
                properties = excluded.properties
            """, (source, target, relationship, prop_json))

    def delete_node(self, node_id: str) -> None:
        """Delete a node and all of its connected edges (handled by CASCADE)."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM graph_nodes WHERE id = ?", (node_id,))

    def delete_edge(self, source: str, target: str, relationship: str) -> None:
        """Delete a specific edge."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            DELETE FROM graph_edges 
            WHERE source = ? AND target = ? AND relationship = ?
            """, (source, target, relationship))

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a node's properties by its ID."""
        with get_db_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM graph_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "type": row["type"],
                "name": row["name"],
                "properties": json.loads(row["properties"]) if row["properties"] else {}
            }

    def _neighbors_with_conn(self, conn: sqlite3.Connection, node_id: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        cursor = conn.cursor()
        cursor.execute("""
        SELECT e.target as id, e.relationship, e.properties as edge_props,
               n.type, n.name, n.properties as node_props
        FROM graph_edges e
        JOIN graph_nodes n ON e.target = n.id
        WHERE e.source = ?
        """, (node_id,))
        
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "relationship": row["relationship"],
                "direction": "outgoing",
                "edge_properties": json.loads(row["edge_props"]) if row["edge_props"] else {},
                "node_properties": json.loads(row["node_props"]) if row["node_props"] else {}
            })
            
        cursor.execute("""
        SELECT e.source as id, e.relationship, e.properties as edge_props,
               n.type, n.name, n.properties as node_props
        FROM graph_edges e
        JOIN graph_nodes n ON e.source = n.id
        WHERE e.target = ?
        """, (node_id,))
        
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "relationship": row["relationship"],
                "direction": "incoming",
                "edge_properties": json.loads(row["edge_props"]) if row["edge_props"] else {},
                "node_properties": json.loads(row["node_props"]) if row["node_props"] else {}
            })
            
        return results

    def neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        """Get all adjacent nodes connected by incoming or outgoing edges."""
        with get_db_conn() as conn:
            return self._neighbors_with_conn(conn, node_id)

    def path(self, start_id: str, end_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """Finds shortest path using BFS with reusable DB connection."""
        if start_id == end_id:
            return [start_id]
            
        queue: deque[List[str]] = deque([[start_id]])
        visited: Set[str] = {start_id}
        
        with get_db_conn() as conn:
            while queue:
                current_path = queue.popleft()
                current_node = current_path[-1]
                
                if current_node == end_id:
                    return current_path
                    
                if len(current_path) >= max_depth:
                    continue
                    
                for neighbor in self._neighbors_with_conn(conn, current_node):
                    neighbor_id = neighbor["id"]
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        new_path = list(current_path) + [neighbor_id]
                        queue.append(new_path)
                        
        return None

    def find_path(self, start_id: str, end_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """Alias for multi-hop path query traversal."""
        return self.path(start_id, end_id, max_depth=max_depth)

    def extract_subgraph(self, center_node_id: str, depth: int = 2) -> Dict[str, Any]:
        """Extracts subgraph neighborhood around a center node up to N hops."""
        nodes: Dict[str, Any] = {}
        edges: List[Dict[str, Any]] = []
        visited_nodes: Set[str] = {center_node_id}
        queue: deque = deque([(center_node_id, 0)])

        with get_db_conn() as conn:
            center_node = self.get_node(center_node_id)
            if center_node:
                nodes[center_node_id] = center_node

            while queue:
                curr_id, curr_depth = queue.popleft()
                if curr_depth >= depth:
                    continue

                for nbr in self._neighbors_with_conn(conn, curr_id):
                    nbr_id = nbr["id"]
                    edges.append({
                        "source": curr_id if nbr["direction"] == "outgoing" else nbr_id,
                        "target": nbr_id if nbr["direction"] == "outgoing" else curr_id,
                        "relationship": nbr["relationship"]
                    })
                    if nbr_id not in visited_nodes:
                        visited_nodes.add(nbr_id)
                        node_obj = self.get_node(nbr_id)
                        if node_obj:
                            nodes[nbr_id] = node_obj
                        queue.append((nbr_id, curr_depth + 1))

        return {"nodes": list(nodes.values()), "edges": edges}

