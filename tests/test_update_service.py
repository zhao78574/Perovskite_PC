import pytest

from update_service import UpdateError, is_newer


def test_version_comparison_ignores_v_prefix():
    assert is_newer("1.4.2", "v1.4.3")
    assert not is_newer("1.4.3", "1.4.3")
    assert not is_newer("1.4.3", "1.4.2")


def test_invalid_version_fails_closed():
    with pytest.raises(UpdateError):
        is_newer("1.4.2", "latest")
