import chromadb
import uuid
import os
import hashlib
import re
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "db")

class VectorStore:
    def __init__(self):
        # Operates locally, creating the ./db folder if it doesn't exist
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name="subconscious_thoughts")

    def _normalize_thought(self, text):
        text = text.strip().lower()
        return re.sub(r'\s+', ' ', text)

    def _hash_thought(self, text):
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def is_duplicate(self, text):
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

    def process_thought(self, text, embedding):
        """
        Executes the crucial Order of Operations:
        1. QUERY FIRST (to prevent retrieving itself)
        2. UPSERT SECOND (persist the new thought)
        
        Returns the top 3 closest matches.
        """
        normalized_text = self._normalize_thought(text)
        text_hash = self._hash_thought(normalized_text)
        is_duplicate = self.is_duplicate(text)

        matches = []
        
        # 1. QUERY FIRST
        if self.collection.count() > 0:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=min(3, self.collection.count())
            )
            # Safely extract documents if they exist
            if results and 'documents' in results and results['documents']:
                matches = results['documents'][0]
        
        # 2. UPSERT SECOND
        if not is_duplicate:
            doc_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{"hash": text_hash, "timestamp": timestamp}]
            )
        
        return matches

    def get_all_thoughts(self):
        """
        Retrieves all thoughts, IDs, and embeddings from the collection.
        Used by the visualization dashboard.
        """
        if self.collection.count() == 0:
            return {"ids": [], "documents": [], "embeddings": []}
            
        return self.collection.get(
            include=["documents", "embeddings", "metadatas"]
        )