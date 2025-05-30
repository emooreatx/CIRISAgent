def test_memory_handlers_registered():
    from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
    from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
    dispatcher = build_action_dispatcher()
    # Verify all memory handlers are registered
    assert HandlerActionType.MEMORIZE in dispatcher.handlers
    assert HandlerActionType.RECALL in dispatcher.handlers
    assert HandlerActionType.FORGET in dispatcher.handlers
