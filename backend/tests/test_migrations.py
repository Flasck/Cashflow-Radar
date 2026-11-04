import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.connection import Base
from sqlalchemy import inspect, text


@pytest.mark.asyncio
async def test_initial_migration_round_trip(test_engine):
    path = (
        Path(__file__).parents[1] / "migrations" / "versions" / "0001_initial_schema.py"
    )
    spec = importlib.util.spec_from_file_location("initial_schema", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def apply(connection, direction):
        with Operations.context(MigrationContext.configure(connection)):
            getattr(migration, direction)()

    def verify(connection):
        inspector = inspect(connection)
        assert set(inspector.get_table_names(schema="migration_test")) == set(
            Base.metadata.tables
        )
        for name, table in Base.metadata.tables.items():
            columns = inspector.get_columns(name, schema="migration_test")
            assert {column["name"] for column in columns} == set(table.columns.keys())
            for column in columns:
                assert column["nullable"] == table.columns[column["name"]].nullable
        checks = inspector.get_check_constraints("invitations", schema="migration_test")
        assert any(check["name"] == "check_invitation_response" for check in checks)
        constraints = inspector.get_unique_constraints("users", schema="migration_test")
        assert any(
            item["name"] == "uq_users_email" and item["column_names"] == ["email"]
            for item in constraints
        )
        indexes = inspector.get_indexes("users", schema="migration_test")
        assert any(
            index["name"] == "ix_users_email" and not index["unique"]
            for index in indexes
        )

    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(text("CREATE SCHEMA migration_test"))
            await connection.execute(text("SET LOCAL search_path TO migration_test"))
            for _ in range(2):
                await connection.run_sync(apply, "upgrade")
                await connection.run_sync(verify)
                await connection.run_sync(apply, "downgrade")
                names = await connection.run_sync(
                    lambda conn: inspect(conn).get_table_names(schema="migration_test")
                )
                assert names == []
        finally:
            await transaction.rollback()
