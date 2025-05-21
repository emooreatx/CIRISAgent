from ciris_engine.formatters.user_profiles import format_user_profiles


def test_format_user_profiles_basic():
    profiles = {
        "user1": {"nick": "Alpha", "interest": "python", "channel": "general"},
        "user2": {"name": "Beta", "channel": "random"},
    }
    block = format_user_profiles(profiles)
    assert "IMPORTANT USER CONTEXT" in block
    assert "User 'user1': Name/Nickname: 'Alpha'" in block
    assert "Interest: 'python...'" in block
    assert "Primary Channel: 'general'" in block
    assert "User 'user2': Name/Nickname: 'Beta'" in block
