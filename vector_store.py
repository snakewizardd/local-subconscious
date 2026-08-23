import chromadb
import uuid
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "db")

class VectorStore:
    def __init__(self):
        # Operates locally, creating the ./db folder if it doesn't exist
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.collection = self.client.get_or_create_collection(name="subconscious_thoughts")

    def process_thought(self, text, embedding):
        """
        Executes the crucial Order of Operations:
        1. QUERY FIRST (to prevent retrieving itself)
        2. UPSERT SECOND (persist the new thought)
        
        Returns the top 3 closest matches.
        """
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
        doc_id = str(uuid.uuid4())
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text]
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
            include=["documents", "embeddings"]
        )