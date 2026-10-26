"""Runs the project's static checks as tests (no real libraries needed, so this runs anywhere)."""
import pytest

from scripts import static_checks as sc


@pytest.mark.parametrize(
    "check",
    [
        sc.check_compile,
        sc.check_imports_resolve,
        sc.check_no_import_cycles,
        sc.check_env_matches_settings,
        sc.check_no_secrets_committed,
        sc.check_secret_access_is_limited,
        sc.check_logging_is_safe,
        sc.check_no_dangerous_calls,
        sc.check_test_overrides_target_real_dependencies,
        sc.check_call_signatures,
        sc.check_routes_are_documented,
    ],
)
def test_static_check_passes(check):
    result = check()
    assert result.problems == [], result.name + "\n" + "\n".join(result.problems)
