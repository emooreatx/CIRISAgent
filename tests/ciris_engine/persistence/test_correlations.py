import os
import tempfile
from ciris_engine.persistence import initialize_database
from ciris_engine.persistence import (
    add_correlation,
    update_correlation,
    get_correlation,
)
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus


def temp_db_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name


def test_add_and_update_correlation():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        corr = ServiceCorrelation(
            correlation_id="corr1",
            service_type="test",
            handler_name="tester",
            action_type="send",
            request_data={"a": 1},
        )
        add_correlation(corr, db_path=db_path)
        fetched = get_correlation("corr1", db_path=db_path)
        assert fetched is not None
        assert fetched.request_data["a"] == 1
        update_correlation("corr1", response_data={"ok": True}, status=ServiceCorrelationStatus.COMPLETED, db_path=db_path)
        updated = get_correlation("corr1", db_path=db_path)
        assert updated.response_data["ok"] is True
        assert updated.status == ServiceCorrelationStatus.COMPLETED
    finally:
        os.unlink(db_path)
