import unittest
from safecor import ResponseFactory, ComponentState


class TestResponseFactory(unittest.TestCase):

    def test_create_entry_component_state(self):
        entry = ResponseFactory.create_entry_component_state("id", "label", "name", ComponentState.STARTING, "core")

        self.assertEqual(entry.get("id", ""), "id")
        self.assertEqual(entry.get("label", ""), "label")
        self.assertEqual(entry.get("domain_name", ""), "name")
        self.assertEqual(entry.get("state", ""), ComponentState.STARTING.value)
        self.assertEqual(entry.get("type", ""), "core")

    def test_create_response_component_state(self):
        entry1 = ResponseFactory.create_entry_component_state("id1", "label1", "name1", ComponentState.STARTING, "core")
        entry2 = ResponseFactory.create_entry_component_state("id2", "label2", "name2", ComponentState.ERROR, "business")
        entry3 = ResponseFactory.create_entry_component_state("id3", "label3", "name3", ComponentState.READY, "core")

        payload = ResponseFactory.create_response_component_state([entry1, entry2, entry3])

        self.assertEqual(len(payload.get("components", [])), 3)

        entry1_ = payload["components"][0]
        entry2_ = payload["components"][1]
        entry3_ = payload["components"][2]

        self.assertEqual(entry1, entry1_)
        self.assertEqual(entry2, entry2_)
        self.assertEqual(entry3, entry3_)