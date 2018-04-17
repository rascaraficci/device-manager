from __future__ import with_statement
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy import MetaData, Table, ForeignKeyConstraint, Index
from logging.config import fileConfig
import logging

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from flask import current_app
config.set_main_option('sqlalchemy.url', current_app.config.get('SQLALCHEMY_DATABASE_URI'))
target_metadata = current_app.extensions['migrate'].db.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

from DeviceManager.TenancyManager import list_tenants

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
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()


def include_schemas(names):
    # produce an include object function that filters on the given schemas
    def include_object(object, name, type_, reflected, compare_to):
        # print("got data {} type: {} name: {}, compare_to: {}".format(object, type_, name, compare_to))
        if type_ == "table":
            print("got table {} {} {}".format(name, object.schema, names))
            return object.schema in names
        return True

    return include_object


def _get_table_key(name, schema):
    if schema is None:
        return name
    else:
        return schema + "." + name


def tometadata(table, metadata, schema):
    key = _get_table_key(table.name, schema)
    if key in metadata.tables:
        return metadata.tables[key]

    args = []
    for c in table.columns:
        args.append(c.copy(schema=schema))
    new_table = Table(
        table.name, metadata, schema=schema,
        *args, **table.kwargs
    )
    for c in table.constraints:
        if isinstance(c, ForeignKeyConstraint):
            constraint_schema = schema
        else:
            constraint_schema = schema
        new_table.append_constraint(
            c.copy(schema=constraint_schema, target_table=new_table))

    for index in table.indexes:
        # skip indexes that would be generated
        # by the 'index' flag on Column
        if len(index.columns) == 1 and \
                list(index.columns)[0].index:
            continue
        Index(index.name,
              unique=index.unique,
              *[new_table.c[col] for col in index.columns.keys()],
              **index.kwargs)

    return table._schema_item_copy(new_table)

def get_context(tenant=None):
    global target_metadata
    if tenant is not None:
        metax = MetaData()
        for table in target_metadata.tables.values():
            tometadata(table, metax, tenant)
        target_metadata = metax

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    engine = engine_from_config(config.get_section(config.config_ini_section),
                                prefix='sqlalchemy.',
                                poolclass=pool.NullPool)
    connection = engine.connect()
    # connection.execution_options(schema_translate_map={None: tenant})
    context.configure(connection=connection,
                      target_metadata=target_metadata,
                      process_revision_directives=process_revision_directives,
                      include_schemas=True,
                      include_object=include_schemas([tenant]),
                      **current_app.extensions['migrate'].configure_args)
    return context, connection

def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    tenants = []
    ctx, conn = get_context()
    try:
        tenants = list_tenants(conn)
    finally:
        conn.close()

    for tenant in tenants:
        context, connection = get_context()
        try:
            logger.info('About to migrate tenant {}'.format(tenant))
            connection.execute('set search_path to "{}"'.format(tenant))
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
