import chromadb
import uuid
import os
import hashlib
import re
import threading
from datetime import datetime, timezone

try:
    from chromadb.api.client import SharedSystemClient as _ChromaSharedSystemClient
except ImportError:  # keep working on older chromadb builds
    _ChromaSharedSystemClient = None

DB_PATH = os.path.join(os.path.dirname(__file__), "db")
_STORE_LOCK = threading.Lock()

DEFAULT_COLLECTION = "subconscious_thoughts"
ENTITY_PREFIX = "entity_"

def entity_collection_name(entity):
    """Sanitize an entity name into a valid, prefixed Chroma collection name."""
    slug = re.sub(r'[^a-zA-Z0-9._-]+', '-', str(entity).strip().lower()).strip('-._')
    if not slug:
        raise ValueError("Entity name must contain at least one alphanumeric character.")
    return (ENTITY_PREFIX + slug)[:63].rstrip('-._')

def list_entities():
    """Return the default collection plus all entity_* collections with counts."""
    entities = []
    with _STORE_LOCK:
        try:
            client = chromadb.PersistentClient(path=DB_PATH)
            names = []
            for col in client.list_collections():
                names.append(col if isinstance(col, str) else getattr(col, "name", None))
            for name in names:
                if name == DEFAULT_COLLECTION:
                    entity = "subconscious"
                elif name and name.startswith(ENTITY_PREFIX):
                    entity = name[len(ENTITY_PREFIX):]
                else:
                    continue
                try:
                    count = client.get_collection(name).count()
                except Exception:
                    count = 0
                entities.append({
                    "entity": entity,
                    "collection": name,
                    "count": count,
                    "default": name == DEFAULT_COLLECTION
                })
        except Exception:
            return entities
    entities.sort(key=lambda item: (not item["default"], item["entity"]))
    return entities

class VectorStore:
    def __init__(self, collection_name=DEFAULT_COLLECTION):
        # Operates locally, creating the ./db folder if it doesn't exist
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name=self.collection_name)

    def _ensure_client(self):
        if not hasattr(self, "client") or self.client is None:
            self.client = chromadb.PersistentClient(path=DB_PATH)

    def _refresh_collection(self):
        self._ensure_client()
        try:
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
        except (chromadb.errors.InternalError, ValueError, TypeError):
            self.collection = None

    def _normalize_thought(self, text):
        text = text.strip().lower()
        return re.sub(r'\s+', ' ', text)

    def _hash_thought(self, text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def is_duplicate(self, text):
        try:
            normalized_text = self._normalize_thought(text)
            text_hash = self._hash_thought(normalized_text)
            existing = self.collection.get(where={"hash": text_hash})
            if existing and existing.get('ids'):
                return True

            # Entries written before hash metadata was introduced must still deduplicate.
            legacy_entries = self.collection.get(include=["documents"])
            return any(
                self._normalize_thought(document) == normalized_text
                for document in legacy_entries.get("documents", [])
                if isinstance(document, str)
            )
        except (AttributeError, chromadb.errors.InternalError, ValueError, TypeError):
            self._refresh_collection()
            return False

    def process_thought(self, text, embedding):
        """
        Executes the crucial Order of Operations:
        1. QUERY FIRST (to prevent retrieving itself)
        2. UPSERT SECOND (persist the new thought)
        
        Returns the top 3 closest matches.
        """
        normalized_text = self._normalize_thought(text)
        text_hash = self._hash_thought(normalized_text)

        matches = []

        try:
            if self.collection is not None and self.collection.count() > 0:
                results = self.collection.query(
                    query_embeddings=[embedding],
                    n_results=min(3, self.collection.count())
                )
                if results and 'documents' in results and results['documents']:
                    matches = results['documents'][0]
        except (AttributeError, chromadb.errors.InternalError, ValueError, TypeError):
            self._refresh_collection()
            matches = []

        doc_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            if self.collection is None:
                self._refresh_collection()
            if self.collection is None:
                return matches

            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{"hash": text_hash, "timestamp": timestamp}]
            )
        except (AttributeError, chromadb.errors.InternalError, ValueError, TypeError):
            self._refresh_collection()
            try:
                if self.collection is not None:
                    self.collection.add(
                        ids=[doc_id],
                        embeddings=[embedding],
                        documents=[text],
                        metadatas=[{"hash": text_hash, "timestamp": timestamp}]
                    )
            except (AttributeError, chromadb.errors.InternalError, ValueError, TypeError):
                return matches

        return matches

    def get_all_thoughts(self):
        """
        Retrieves all thoughts, IDs, and embeddings from the collection.
        Used by the visualization dashboard.
        """
        empty = {"ids": [], "documents": [], "embeddings": [], "metadatas": []}
        # Serialize the cache-bust + reopen; chromadb's SharedSystemClient dict
        # is not thread-safe when cleared under concurrent requests.
        with _STORE_LOCK:
            if _ChromaSharedSystemClient is not None:
                try:
                    _ChromaSharedSystemClient.clear_system_cache()
                except Exception:
                    pass
            try:
                client = chromadb.PersistentClient(path=DB_PATH)
                collection = client.get_or_create_collection(name=self.collection_name)
                self.client = client
                self.collection = collection
            except (AttributeError, KeyError, chromadb.errors.InternalError, ValueError, TypeError):
                return empty

            try:
                if collection.count() == 0:
                    return empty
                data = collection.get(include=["documents", "embeddings", "metadatas"])
                if not isinstance(data, dict):
                    return empty
                for key in ("ids", "documents", "embeddings", "metadatas"):
                    data.setdefault(key, [])
                return data
            except (AttributeError, KeyError, chromadb.errors.InternalError, ValueError, TypeError):
                return empty