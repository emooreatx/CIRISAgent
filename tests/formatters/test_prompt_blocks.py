from ciris_engine.formatters.prompt_blocks import (
    format_parent_task_chain,
    format_thoughts_chain,
    format_system_prompt_blocks,
    format_user_prompt_blocks,
)


def test_format_parent_task_chain_and_thoughts_chain():
    parents = [
        {"description": "Root", "task_id": "1"},
        {"description": "Direct", "task_id": "2"},
    ]
    parent_block = format_parent_task_chain(parents)
    assert "=== Parent Task Chain ===" in parent_block
    assert "Root Task: Root (Task ID: 1)" in parent_block
    assert "Direct Parent: Direct (Task ID: 2)" in parent_block

    thoughts = [
        {"content": "first"},
        {"content": "active"},
    ]
    thought_block = format_thoughts_chain(thoughts)
    assert "=== Thoughts Under Consideration ===" in thought_block
    assert "Thought 1: first" in thought_block
    assert "Active Thought: active" in thought_block


def test_format_prompt_blocks_order():
    system_message = format_system_prompt_blocks(
        "=== Task History ===\nA",
        "=== System Snapshot ===\nB",
        "=== User Profiles ===\nC",
        escalation_guidance_block="=== Escalation Guidance ===\nD",
        system_guidance_block="=== System Guidance ===\nE",
    )
    expected_order = [
        "Task History",
        "System Guidance",
        "Escalation Guidance",
        "System Snapshot",
        "User Profiles",
    ]
    for idx, label in enumerate(expected_order):
        assert system_message.find(label) < system_message.find(expected_order[idx + 1]) if idx + 1 < len(expected_order) else True

    user_message = format_user_prompt_blocks(
        "=== Parent Task Chain ===\nA",
        "=== Thoughts Under Consideration ===\nB",
        schema_block="=== Schema ===\nC",
    )
    expected_order_user = [
        "Parent Task Chain",
        "Thoughts Under Consideration",
        "Schema",
    ]
    for idx, label in enumerate(expected_order_user):
        assert user_message.find(label) < user_message.find(expected_order_user[idx + 1]) if idx + 1 < len(expected_order_user) else True
