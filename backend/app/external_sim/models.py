# SQLAlchemy models standing in for external verification providers:
# a synthetic BVN registry, a synthetic PEP/sanctions list, and a synthetic
# corporate registry.
#
# Kept in a dedicated Postgres schema ("external_sim") rather than the main
# app schema, since these are stand-ins for third-party systems, not part of
# the application's own data model. Each model will set:
#   __table_args__ = {"schema": "external_sim"}
#
# Left empty intentionally — waiting on field specs before defining columns.
#
# from app.core.database import Base
