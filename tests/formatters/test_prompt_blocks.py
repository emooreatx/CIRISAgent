from ciris_engine.formatters.prompt_blocks import (
    format_parent_task_chain,
    format_thoughts_chain,
    format_system_prompt_blocks,
    format_user_prompt_blocks,
)


def test_format_parent_task_chain():
    chain = [
        {"description": "root desc", "task_id": "1"},
        {"description": "child", "task_id": "2"},
    ]
    block = format_parent_task_chain(chain)
    assert block.startswith("=== Parent Task Chain ===")
    assert "Root Task" in block
    assert "Direct Parent" in block


def test_format_thoughts_chain():
    thoughts = [{"content": "first"}, {"content": "second"}]
    block = format_thoughts_chain(thoughts)
    assert block.startswith("=== Thoughts Under Consideration ===")
    assert "Thought 1: first" in block
    assert "Active Thought: second" in block


def test_prompt_block_ordering():
    sys_block = format_system_prompt_blocks(
        "IDENTITY",
        "TASK",
        "SNAP",
        "PROFILES",
        "ESCALATE",
        "GUIDE",
    )
    assert sys_block.split("\n\n")[0] == "IDENTITY"
    user_block = format_user_prompt_blocks("PARENT", "THOUGHTS", "SCHEMA")
    parts = user_block.split("\n\n")
    assert parts[0] == "PARENT"
    assert parts[1] == "THOUGHTS"
    assert parts[2] == "SCHEMA"
