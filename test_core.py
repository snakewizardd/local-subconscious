import unittest
from unittest.mock import patch

import chromadb

import explorer
import vector_store
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


class RecordingCollection:
    def __init__(self):
        self.added = None

    def count(self):
        return 0

    def add(self, **kwargs):
        self.added = kwargs


class ExplorerTests(unittest.TestCase):
    def test_graph_accepts_legacy_null_metadata(self):
        store = FakeStore({
            "ids": ["legacy"],
            "documents": ["A legacy thought"],
            "embeddings": [[1.0, 0.0]],
            "metadatas": [None],
        })

        with patch.object(explorer, "_store_for", return_value=store):
            graph = explorer.get_graph()

        self.assertEqual(graph, {
            "nodes": [{
                "id": "legacy",
                "label": "A legacy thought",
                "text": "A legacy thought",
                "title": "A legacy thought",
                "full_text": "A legacy thought",
                "timestamp": None,
            }],
            "edges": [],
        })

    def test_graph_limits_each_node_to_strongest_neighbors(self):
        store = FakeStore({
            "ids": ["a", "b", "c", "d"],
            "documents": ["A", "B", "C", "D"],
            "embeddings": [
                [1.0, 0.0],
                [0.99, 0.10],
                [0.98, 0.20],
                [0.0, 1.0],
            ],
            "metadatas": [
                {"person_id": "p001"},
                {"person_id": "p002"},
                {"person_id": "p003"},
                {"person_id": "p004"},
            ],
        })

        with patch.object(explorer, "_store_for", return_value=store):
            graph = explorer.get_graph(threshold=0.0, max_neighbors=1)

        degrees = {node_id: 0 for node_id in ("a", "b", "c", "d")}
        for edge in graph["edges"]:
            degrees[edge["from"]] += 1
            degrees[edge["to"]] += 1

        self.assertLessEqual(max(degrees.values()), 1)
        self.assertEqual(graph["nodes"][0]["person_id"], "p001")
        self.assertIn("Person: p001", graph["nodes"][0]["full_text"])

    def test_delete_entity_removes_cached_store(self):
        explorer._entity_stores["entity_research_network"] = object()

        with patch.object(explorer, "delete_entity_collection", return_value=True):
            result = explorer.delete_entity("research_network")

        self.assertEqual(result, {
            "status": "deleted",
            "entity": "research_network",
        })
        self.assertNotIn("entity_research_network", explorer._entity_stores)

    def test_duplicate_check_compares_legacy_documents(self):
        store = VectorStore.__new__(VectorStore)
        store.collection = FakeCollection(["  A legacy thought  "])

        self.assertTrue(store.is_duplicate("a LEGACY\nthought"))

    def test_process_thought_persists_custom_metadata(self):
        store = VectorStore.__new__(VectorStore)
        store.collection = RecordingCollection()

        store.process_thought(
            "An atomic claim",
            [1.0, 0.0],
            {"person_id": "p001", "claim_type": "FACT"},
        )

        metadata = store.collection.added["metadatas"][0]
        self.assertEqual(metadata["person_id"], "p001")
        self.assertEqual(metadata["claim_type"], "FACT")
        self.assertIn("hash", metadata)
        self.assertIn("timestamp", metadata)

    def test_get_all_thoughts_handles_chromadb_internal_error(self):
        class BrokenCollection:
            def count(self):
                return 1

            def get(self, *args, **kwargs):
                raise chromadb.errors.InternalError("Error finding id")

        class FakeClient:
            def get_or_create_collection(self, name):
                return BrokenCollection()

        store = VectorStore.__new__(VectorStore)

        with patch.object(vector_store.chromadb, "PersistentClient", return_value=FakeClient()):
            self.assertEqual(store.get_all_thoughts(), {
                "ids": [],
                "documents": [],
                "embeddings": [],
                "metadatas": [],
            })


if __name__ == "__main__":
    unittest.main()