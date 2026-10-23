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

## Part 6 - users and API keys
- Stored only a SHA-256 hash of each API key. SHA-256 is fine because keys are
  long and random; slow hashes like bcrypt exist for guessable human passwords.
- Used secrets (not random) to generate keys, since they must be unguessable.
- Handled duplicate emails by catching the database's IntegrityError instead
  of checking first, which avoids a race between two simultaneous signups.
