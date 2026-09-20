import json
import shutil
import tempfile
from pathlib import Path

import pytest
from core.session import LocalDiskAdapter, SessionStore, get_session_store
from core.ui import load_session, save_session, delete_session, conversation_history


@pytest.fixture
def temp_store(tmp_path):
    adapter = LocalDiskAdapter(base_dir=tmp_path)
    store = SessionStore(local_adapter=adapter, remote_adapter=None)
    return store, tmp_path


def test_session_store_save_and_load(temp_store):
    store, tmp_path = temp_store
    session_id = "test-session-1"
    messages = [{"role": "user", "content": "Hello RAG"}, {"role": "assistant", "content": "Hi there!"}]
    files = ["doc.pdf"]
    urls = ["https://example.com"]
    chunk_count = 5

    store.save(session_id, messages, files, urls, chunk_count, user_id="user_123")
    loaded = store.load(session_id)

    assert loaded["user_id"] == "user_123"
    assert len(loaded["messages"]) == 2
    assert loaded["uploaded_file_names"] == ["doc.pdf"]
    assert loaded["chunk_count"] == 5


def test_session_store_list_history(temp_store):
    store, tmp_path = temp_store
    session_id = "test-session-2"
    messages = [{"role": "user", "content": "Explain quantum computing"}, {"role": "assistant", "content": "Quantum..."}]

    store.save(session_id, messages, [], [], 0, user_id="user_abc")
    history = store.list_history(user_id="user_abc")

    assert len(history) == 1
    assert history[0]["id"] == session_id
    assert "Explain quantum" in history[0]["title"]

    # Other user shouldn't see it
    history_other = store.list_history(user_id="user_xyz")
    assert len(history_other) == 0


def test_session_store_delete(temp_store):
    store, tmp_path = temp_store
    session_id = "test-session-3"
    store.save(session_id, [{"role": "user", "content": "Delete me"}], [], [], 0)

    assert (tmp_path / session_id / "metadata.json").exists()
    store.delete(session_id)
    assert not (tmp_path / session_id).exists()


def test_ui_module_backward_compatibility():
    # Ensure ui.py still exports the expected persistence symbols
    from core.ui import save_session, load_session, delete_session, conversation_history, session_path
    assert callable(save_session)
    assert callable(load_session)
    assert callable(delete_session)
    assert callable(conversation_history)
    assert callable(session_path)
