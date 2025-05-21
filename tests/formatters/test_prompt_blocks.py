from ciris_engine.formatters.prompt_blocks import (
    format_parent_task_chain,
    format_thoughts_chain,
    format_system_prompt_blocks,
    format_user_prompt_blocks,
)


def test_parent_and_thoughts_chain():
    parents = [
        {"description": "Root desc", "task_id": "1"},
        {"description": "Child desc", "task_id": "2"},
    ]
    block = format_parent_task_chain(parents)
    assert "Root Task" in block
    assert "Direct Parent" in block

    thoughts = [{"content": "first"}, {"content": "second"}]
    tblock = format_thoughts_chain(thoughts)
    assert "Thought 1" in tblock
    assert "Active Thought" in tblock


def test_prompt_block_order():
    system_msg = format_system_prompt_blocks(
        "task", "snap", "profiles", "esc", "guidance"
    )
    assert system_msg.startswith("task")
    assert system_msg.endswith("profiles")

    user_msg = format_user_prompt_blocks("parents", "thoughts", "schema")
    assert user_msg == "parents\n\nthoughts\n\nschema"
