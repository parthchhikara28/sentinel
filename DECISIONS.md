# Decisions

## Part 2 - skeleton
- Chose a package-per-concern layout (api / db / core / worker) over a single
  main.py because the worker must run as a separate process from the API.
- Chose venv + requirements.txt over Poetry: fewer moving parts for a solo
  project.

## Part 5 - models and migrations
- Chose Alembic migrations over Base.metadata.create_all() because create_all
  only works on an empty database; migrations can change a table that already
  holds data and can be rolled back.
- Stored all timestamps as timezone-aware and set defaults in the database so
  every row uses one clock.
- Left the check_results index out on purpose so Part 13 can measure the
  before/after difference.
