"""Integration tests for backend acceptance criteria.

Each ``test_step_*.py`` script targets one ROADMAP phase and runs
end-to-end against a live ``docker compose --profile app up`` stack.
Run them with:

    python -m scripts.integration_tests.test_step_38_recurring

Or directly:

    python scripts/integration_tests/test_step_38_recurring.py
"""
