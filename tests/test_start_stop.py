from test_helpers import is_server_running, start_server_if_not_running, stop_server_if_running


def test_start_and_stop():
    """Test starting and stopping the server."""

    # Ensure a clean state
    stop_server_if_running()

    # Start the server
    start_server_if_not_running()

    # Verify the server is running
    assert is_server_running(), "Server did not start as expected."

    # Stop the server
    stop_server_if_running()

    # Verify the server is stopped
    assert not is_server_running(), "Server did not stop as expected."

    print("Start and Stop Test Passed.")
