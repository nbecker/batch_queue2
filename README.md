
# asyncio-queue

`asyncio-queue` is a Python-based batch queue manager built using `asyncio`. It provides a simple way to manage and schedule tasks locally with support for dynamic CPU allocation, logging, and daemonized operation.

## Features
- **Task Submission:** Submit tasks with configurable environments, working directories, and log files.
- **Dynamic CPU Allocation:** Automatically detects available CPUs or allows manual configuration.
- **Daemonized Server:** Run the server in the background.
- **Task Management:** Start, stop, suspend, resume, or list tasks via a command-line interface (CLI).

---

## Installation

Install the package from PyPI:
```
pip install asyncio-queue
```

Alternatively, install it from the source:
```
hg clone https://hg.sr.ht/~ndbecker2/asyncio-queue
cd asyncio-queue
pip install .
```

---

## Usage

### Starting the Server

Start the server with auto-detected CPUs:
```
asyncio-queue start
```

Start the server with a specific number of CPUs (e.g., 4):
```
asyncio-queue start --ncpu=4
```

Start the server on a custom port:
```
asyncio-queue start --port=9000
```

Start the server in the background (daemonized):
```
asyncio-queue start --daemon
```

---

### Submitting Tasks

Submit a task to the queue:
```
asyncio-queue submit --user yourname echo "Hello, World!"
```

Submit a task with a specific working directory:
```
asyncio-queue submit --user yourname --path /home/yourname myscript.sh
```

Submit a task with environment variables:
```
asyncio-queue submit --user yourname --env '{"MY_VAR": "value"}' python myscript.py
```

Submit a task and log outputs:
```
asyncio-queue submit --user yourname --log-stdout stdout.log --log-stderr stderr.log python myscript.py
```

---

### Listing Tasks

View all tasks in the queue:
```
asyncio-queue list
```

Example output:
```
CPUs: 4 available, 2 used, 2 free
Active tasks:
  Task(id=1, command=['echo', 'Hello, World!'], user='yourname', active=True)
Queued tasks:
  Task(id=2, command=['python', 'myscript.py'], user='yourname', active=False)
Stopped tasks:
```

---

### Stopping the Server

Stop the server and all running tasks:
```
asyncio-queue stop
```

---

### Managing Task Execution

Suspend a running task:
```
asyncio-queue suspend <task_id>
```

Resume a suspended task:
```
asyncio-queue resume <task_id>
```

Kill a specific task:
```
asyncio-queue kill <task_id>
```

---

### Configuration Options

- **Dynamic CPU Allocation:** The server auto-detects available CPUs. You can override this with the `--ncpu` option.
- **Custom Logging:** Use the `--log-stdout` and `--log-stderr` options during task submission to capture task output.

---

## Contributing

The source code is available on [SourceHut](https://hg.sr.ht/~ndbecker2/asyncio-queue). Contributions, bug reports, and feature requests are welcome. Please use Mercurial for version control.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
