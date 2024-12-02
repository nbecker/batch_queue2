#!/usr/bin/env python3

import os
import argparse
import signal

import xmlrpc.client
import http.client
import socket

SERVER_SOCKET = "/tmp/batch_queue.sock"

class UnixStreamHTTPConnection(http.client.HTTPConnection):
    """Custom HTTPConnection to use Unix domain sockets."""
    def __init__(self, socket_path, *args, **kwargs):
        super().__init__("localhost", *args, **kwargs)
        self.socket_path = socket_path

    def connect(self):
        """Override connect to use a Unix domain socket."""
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


class UnixStreamTransport(xmlrpc.client.Transport):
    """Custom XML-RPC transport for Unix domain sockets."""
    def __init__(self, socket_path):
        super().__init__()
        self.socket_path = socket_path

    def make_connection(self, host):
        return UnixStreamHTTPConnection(self.socket_path)

import getpass

def submit_task(command, log_stdout, log_stderr):
    username = getpass.getuser()  # Replaces os.getlogin()
    path = os.getcwd()  # Capture the current working directory
    env = dict(os.environ)  # Capture the current environment variables

    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            task_id = proxy.submit_task(command, username, path, env, log_stdout, log_stderr)
            print(f"Task submitted successfully with ID: {task_id}")
        except xmlrpc.client.Fault as err:
            print(f"Failed to submit task: {err}")


def list_tasks():
    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            tasks_info = proxy.list_tasks()
            print("Tasks:")
            print(f"Max CPUs: {tasks_info['max_cpus']}")
            print(f"Active tasks: {tasks_info['active']}")
            print(f"Queued tasks: {tasks_info['queued']}")
            print(f"Paused tasks: {tasks_info['paused']}")
            print(f"Runnable paused tasks: {tasks_info['runnable_paused']}")
        except xmlrpc.client.Fault as err:
            print(f"Failed to list tasks: {err}")

def id_tasks(task_id):
    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            id_info = proxy.id_task(task_id)
            print(f'cmd: {id_info}')
            
        except xmlrpc.client.Fault as err:
            print(f"Failed to id task: {err}")

def kill_tasks(task_ids, signal_type):
    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            result = proxy.kill_tasks(task_ids, int(signal_type))
            for task_id, status in result.items():
                if status:
                    print(f"Task {task_id} killed successfully.")
                else:
                    print(f"Failed to kill task {task_id}.")
        except xmlrpc.client.Fault as err:
            print(f"Failed to kill tasks: {err}")

def suspend_tasks(task_ids):
    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            result = proxy.suspend_tasks(task_ids)
            for task_id, success in result.items():
                if success:
                    print(f"Task {task_id} suspended successfully.")
                else:
                    print(f"Failed to suspend task {task_id}.")
        except xmlrpc.client.Fault as err:
            print(f"Failed to suspend tasks: {err}")

def resume_tasks(task_ids):
    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            result = proxy.resume_tasks(task_ids)
            for task_id, success in result.items():
                if success:
                    print(f"Task {task_id} resumed successfully.")
                else:
                    print(f"Failed to resume task {task_id}.")
        except xmlrpc.client.Fault as err:
            print(f"Failed to resume tasks: {err}")

def stop_server():
    transport = UnixStreamTransport(SERVER_SOCKET)

    # Use the "with" statement to manage the ServerProxy lifecycle
    with xmlrpc.client.ServerProxy("http://localhost", transport=transport, allow_none=True) as proxy:
        try:
            proxy.stop_server()
            print("Server stopped successfully.")
        except xmlrpc.client.Fault as err:
            print(f"Failed to stop server: {err}")

def start_server(max_cpus):
    """Start the batch queue server."""
    import os
    import subprocess

    # Set environment variable for max CPUs
    env = os.environ.copy()
    if max_cpus:
        env["MAX_CPUS"] = str(max_cpus)

    try:
        # Launch the server as a background process
        subprocess.Popen(
            ["python", "-m", "batch_queue2.server"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid  # Start a new session            
        )
        print("Server started successfully.")
    except Exception as e:
        print(f"Failed to start the server: {e}")
        exit(1)

def main():
    parser = argparse.ArgumentParser(description="Batch Queue CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument("--max-cpus", type=int, help="Maximum number of CPUs to use (default: all available)")

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a task")
    submit_parser.add_argument("submit_command", nargs='+', help="The command to run")
    submit_parser.add_argument("--log-stdout", help="File to log stdout")
    submit_parser.add_argument("--log-stderr", help="File to log stderr")

    # List command
    list_parser = subparsers.add_parser("list", help="List all tasks")

    # ID command
    id_parser = subparsers.add_parser("id", help="Give details of task")
    id_parser.add_argument ('task_id', type=int, help='the ID of the task')
    
    # Kill command
    kill_parser = subparsers.add_parser("kill", help="Kill a task")
    kill_parser.add_argument("task_ids", type=int, nargs='+', help="The ID of the task to kill")
    kill_parser.add_argument("--signal", type=int, default=signal.SIGTERM, help="The signal to send to the task")

    # Suspend command
    suspend_parser = subparsers.add_parser("suspend", help="Suspend a task")
    suspend_parser.add_argument("task_ids", type=int, nargs='+', help="The IDs of the tasks to suspend")

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a paused task")
    resume_parser.add_argument("task_ids", type=int, nargs='+', help="The IDs of the tasks to resume")

    # Stop server command
    stop_parser = subparsers.add_parser("stop", help="Stop the server")

    args = parser.parse_args()

    if args.command == "start":
        start_server(args.max_cpus)
    elif args.command == "submit":
        submit_task(args.submit_command, args.log_stdout, args.log_stderr)
    elif args.command == "list":
        list_tasks()
    elif args.command == "id":
        id_tasks(args.task_id)
    elif args.command == "kill":
        kill_tasks(args.task_ids, args.signal)
    elif args.command == "suspend":
        suspend_tasks(args.task_ids)
    elif args.command == "resume":
        resume_tasks(args.task_ids)
    elif args.command == "stop":
        stop_server()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
