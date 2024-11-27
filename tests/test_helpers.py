import subprocess
import time


def is_server_running():
    """Check if the server is running by sending a `list` command."""
    try:
        result = subprocess.run(
            ["batch_queue", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
        )
        return "Tasks:" in result.stdout
    except subprocess.SubprocessError:
        return False


def start_server_if_not_running():
    """Start the server if it is not running."""
    if not is_server_running():
        start_result = subprocess.run(
            ["batch_queue", "start", "--max-cpus", "2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert "Server started successfully" in start_result.stdout, (
            f"Start failed: {start_result.stderr}"
        )
        # Allow time for server initialization
        time.sleep(2)


def stop_server_if_running():
    """Stop the server if it is running."""
    if is_server_running():
        stop_result = subprocess.run(
            ["batch_queue", "stop"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert "Server stopped successfully" in stop_result.stdout, (
            f"Stop failed: {stop_result.stderr}"
        )
