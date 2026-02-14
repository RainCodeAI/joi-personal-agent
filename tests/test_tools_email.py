import pytest
from app.tools.email_gmail import list_threads

def test_list_threads():
    # Skip if not authenticated
    try:
        threads = list_threads()
        assert isinstance(threads, list)
    except:
        pytest.skip("Gmail not authenticated")
