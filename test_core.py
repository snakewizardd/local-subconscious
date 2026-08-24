import unittest

import explorer
from vector_store import VectorStore


class FakeStore:
    def __init__(self, data):
        self.data = data

    def get_all_thoughts(self):
        return self.data


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def get(self, where=None, include=None):
        if where is not None:
            return {"ids": []}
        return {"documents": self.documents}


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.original_store = explorer.vector_store

    def tearDown(self):
        explorer.vector_store = self.original_store

    def test_graph_accepts_legacy_null_metadata(self):
        explorer.vector_store = FakeStore({
            "ids": ["legacy"],
            "documents": ["A legacy thought"],
            "embeddings": [[1.0, 0.0]],
            "metadatas": [None],
        })

        self.assertEqual(explorer.get_graph(), {
            "nodes": [{
                "id": "legacy",
                "label": "A legacy thought",
                "title": "A legacy thought",
                "full_text": "A legacy thought",
                "timestamp": None,
            }],
            "edges": [],
        })

    def test_duplicate_check_compares_legacy_documents(self):
        store = VectorStore.__new__(VectorStore)
        store.collection = FakeCollection(["  A legacy thought  "])

        self.assertTrue(store.is_duplicate("a LEGACY\nthought"))


if __name__ == "__main__":
    unittest.main()