import pytest
from ciris_engine.persistence.maintenance import DatabaseMaintenanceService

def test_maintenance_service_init():
    service = DatabaseMaintenanceService(archive_dir_path="/tmp/archive", archive_older_than_hours=12)
    assert service.archive_dir.name == "archive"
    assert service.archive_older_than_hours == 12
