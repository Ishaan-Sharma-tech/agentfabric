import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from agent_fabric.core.models import MemoryRecord

logger = logging.getLogger("agent_fabric.memory.vector")

__all__ = ["QdrantVectorStore"]

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, PointIdsList, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class QdrantVectorStore:
    """
    Optional semantic memory backend using Qdrant Embedded.
    Requires `pip install agentfabric-sdk[vectors]`.
    """
    def __init__(
        self, 
        collection_name: str = "agent_fabric_memories",
        location: str = ":memory:",
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
        vector_size: int = 384
    ):
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "Qdrant Client is not installed. Please install it using: "
                "pip install agentfabric-sdk[vectors]"
            )
            
        self.collection_name = collection_name
        self.client = QdrantClient(location=location)
        self.embedding_fn = embedding_fn or self._default_embedding
        self.vector_size = vector_size
        self._ensure_collection()

    def _default_embedding(self, text: str) -> List[float]:
        """A simple local embedding fallback (returns deterministic float list of size 384)."""
        size = self.vector_size
        vec = [0.0] * size
        if not text:
            return vec
        for i, char in enumerate(text):
            idx = (ord(char) * (i + 1)) % size
            vec[idx] += 1.0
        norm = sum(x*x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _ensure_collection(self) -> None:
        """Create Qdrant collection if it does not exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )

    def _store_sync(self, record: MemoryRecord) -> None:
        vector = record.embedding or self.embedding_fn(record.text)
        payload = {
            "text": record.text,
            "tags": record.tags,
            "agent_id": record.agent_id,
            "created_at": record.created_at.isoformat(),
            "accessed_at": record.accessed_at.isoformat(),
            "importance_score": record.importance_score,
            "metadata": record.metadata
        }
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=record.id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    async def store(self, record: MemoryRecord) -> None:
        """Embed text and insert/update memory record in Qdrant collection."""
        await asyncio.to_thread(self._store_sync, record)

    def _search_sync(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        query_vector = self.embedding_fn(query)
        qdrant_filter = None
        if filters:
            conditions = []
            if "agent_id" in filters:
                conditions.append(
                    FieldCondition(key="agent_id", match=MatchValue(value=filters["agent_id"]))
                )
            if "tag" in filters:
                conditions.append(
                    FieldCondition(key="tags", match=MatchValue(value=filters["tag"]))
                )
            if conditions:
                qdrant_filter = Filter(must=conditions)
                
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=limit
        )
        
        records = []
        for res in results:
            p = res.payload
            if not p:
                continue
            records.append(
                MemoryRecord(
                    id=str(res.id),
                    text=p["text"],
                    embedding=res.vector if hasattr(res, "vector") else None,
                    tags=p.get("tags", []),
                    metadata=p.get("metadata", {}),
                    agent_id=p.get("agent_id"),
                    created_at=datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")),
                    accessed_at=datetime.fromisoformat(p["accessed_at"].replace("Z", "+00:00")),
                    importance_score=p.get("importance_score", 1.0)
                )
            )
        return records

    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """Perform semantic search using cosine similarity on query embeddings."""
        return await asyncio.to_thread(self._search_sync, query, limit, filters)

    def _delete_sync(self, record_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=[record_id])
        )

    async def delete(self, record_id: str) -> None:
        """Remove a point from Qdrant by ID."""
        await asyncio.to_thread(self._delete_sync, record_id)

    def _list_records_sync(
        self, 
        limit: int = 100, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        qdrant_filter = None
        if filters:
            conditions = []
            if "agent_id" in filters:
                conditions.append(
                    FieldCondition(key="agent_id", match=MatchValue(value=filters["agent_id"]))
                )
            if "tag" in filters:
                conditions.append(
                    FieldCondition(key="tags", match=MatchValue(value=filters["tag"]))
                )
            if conditions:
                qdrant_filter = Filter(must=conditions)
                
        scroll_results, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=qdrant_filter,
            limit=limit,
            with_vectors=True,
            with_payload=True
        )
        
        records = []
        for res in scroll_results:
            p = res.payload
            if not p:
                continue
            records.append(
                MemoryRecord(
                    id=str(res.id),
                    text=p["text"],
                    embedding=res.vector if hasattr(res, "vector") else None,
                    tags=p.get("tags", []),
                    metadata=p.get("metadata", {}),
                    agent_id=p.get("agent_id"),
                    created_at=datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")),
                    accessed_at=datetime.fromisoformat(p["accessed_at"].replace("Z", "+00:00")),
                    importance_score=p.get("importance_score", 1.0)
                )
            )
        return records

    async def list_records(
        self, 
        limit: int = 100, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[MemoryRecord]:
        """List records from Qdrant with optional filtering."""
        return await asyncio.to_thread(self._list_records_sync, limit, filters)

