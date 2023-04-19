"""
This file is auto-generated by Alembic. It was updated manually to:
- set `target_metadata` so that Alembic can read the Fence model and
auto-generate migrations;
- load the Fence configuration in order to set `sqlalchemy.url` to the
configured DB URL;
- lock the DB during migrations to ensure only 1 migration runs at a time.
"""


from alembic import context
import logging
from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool

from userdatamodel import Base

from fence.config import config as fence_config
from fence.settings import CONFIG_SEARCH_FOLDERS


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("fence.alembic")

target_metadata = Base.metadata

fence_config.load(
    config_path=os.environ.get("TEST_CONFIG_PATH"),  # for tests
    search_folders=CONFIG_SEARCH_FOLDERS,  # for deployments
)
config.set_main_option("sqlalchemy.url", str(fence_config["DB"]))


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            if connection.dialect.name == "postgresql":
                logger.info(
                    "Locking database to ensure only 1 migration runs at a time"
                )
                # This prevents 2 fence instances from trying to migrate the same
                # DB at the same time, but does not prevent a job (such as
                # usersync) from updating the DB while a migration is running.
                # Solution based on https://github.com/sqlalchemy/alembic/issues/633
                # TODO lock the DB for all processes during migrations
                connection.execute(
                    f"SELECT pg_advisory_xact_lock({fence_config['DB_MIGRATION_POSTGRES_LOCK_KEY']});"
                )
            else:
                logger.info(
                    "Not running on Postgres: not locking database before migrating"
                )
            context.run_migrations()
        if connection.dialect.name == "postgresql":
            # The lock is released when the transaction ends.
            logger.info("Releasing database lock")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
