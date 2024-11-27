from test_helpers import start_server_if_not_running, stop_server_if_running
import subprocess

def test_submit_and_list():
    """Test submitting tasks and listing them."""

    # Ensure server is running
    start_server_if_not_running()

    # Submit a task
    submit_result = subprocess.run(
        ["batch_queue", "submit", "sleep", "10"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert "Task submitted successfully" in submit_result.stdout, f"Submit failed: {submit_result.stderr}"

    # List tasks
    list_result = subprocess.run(
        ["batch_queue", "list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert "Active tasks:" in list_result.stdout, "List output doesn't contain 'Active tasks'."
    assert "Queued tasks:" in list_result.stdout, "List output doesn't contain 'Queued tasks'."

    print("Submit and List Test Passed.")

    # Stop the server for cleanup
    stop_server_if_running()
