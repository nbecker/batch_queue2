#!/usr/bin/env python3

import os
import signal
import logging
import asyncio
import xmlrpc.client
import xmlrpc.server
from aiohttp import web

logging.basicConfig(
    filename=os.path.expanduser("~/batch_queue.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class Task:
    def __init__(self, task_id, command, user, path, env, log_stdout=None, log_stderr=None):
        self.task_id = task_id
        self.command = command
        self.user = user
        self.path = path
        self.env = env
        self.log_stdout = log_stdout
        self.log_stderr = log_stderr
        self.process = None
        self.runnable = True

class TaskManager:
    def __init__(self, max_cpus):
        self.max_cpus = max_cpus
        self.task_counter = 0
        self.active_tasks = []
        self.queued_tasks = []
        self.paused_tasks = []

    async def submit_task(self, command, user, path, env, log_stdout, log_stderr):
        task_id = self.task_counter
        self.task_counter += 1
        task = Task(task_id, command, user, path, env, log_stdout, log_stderr)
        self.queued_tasks.append(task)
        logging.info(f"Task {task_id} submitted: {command}")

        # Schedule tasks to start any available ones
        await self.schedule_tasks()
        return task_id

    async def schedule_tasks(self):
        logging.info(f"Scheduling tasks: active={len(self.active_tasks)}, queued={len(self.queued_tasks)}, paused={len(self.paused_tasks)}")

        stoppable_tasks = [task for task in self.active_tasks if not task.runnable]
        for task in stoppable_tasks:
            os.kill(task.process.pid, signal.SIGSTOP)
            self.active_tasks.remove(task)
            self.paused_tasks.append(task)
            logging.info (f'stopping task: {task.task_id}')

        runnable_tasks = [task for task in self.paused_tasks if task.runnable]
        while len(self.active_tasks) < self.max_cpus and (self.queued_tasks or runnable_tasks):
            if runnable_tasks:
                task = runnable_tasks.pop(0)
                self.paused_tasks.remove(task)
                logging.info(f"Resuming paused task: {task.task_id}")
                os.kill(task.process.pid, signal.SIGCONT)
                self.active_tasks.append(task)
            else:
                task = self.queued_tasks.pop(0)
                await self.run_task(task)
            
    async def run_task(self, task):
        stdout = open(task.log_stdout, "w") if task.log_stdout else asyncio.subprocess.DEVNULL
        stderr = open(task.log_stderr, "w") if task.log_stderr else asyncio.subprocess.DEVNULL

        try:
            task.process = await asyncio.create_subprocess_exec(
                *task.command,
                cwd=task.path,
                env=task.env,
                stdout=stdout,
                stderr=stderr,
                preexec_fn=os.setsid
            )
            self.active_tasks.append(task)
            logging.info(f"Task {task.task_id} process started with PID: {task.process.pid}")

            # Add a callback to handle task completion without blocking the event loop
            asyncio.create_task(self.monitor_task(task))
        except Exception as e:
            logging.error(f"Failed to start task {task.task_id}: {e}")

    async def monitor_task(self, task):
        await task.process.wait()  # Wait for the subprocess to complete

        # Only attempt to remove the task if it is still in the active list
        if task in self.active_tasks:
            self.active_tasks.remove(task)

        # If the task process has been killed, process will be None.
        if task.process is None:
            logging.info(f"Task {task.task_id} was killed.")
        elif task.process.returncode == 0:
            logging.info(f"Task {task.task_id} completed successfully.")
        else:
            logging.error(f"Task {task.task_id} failed with return code {task.process.returncode}.")

        # Schedule any tasks waiting in the queue
        await self.schedule_tasks()

    async def suspend_tasks(self, task_ids):
        results = {}
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task:
                if task in self.active_tasks:
                    # Suspend an active task
                    # Mark as not runnable, let scheduler do the rest
                    task.runnable = False
                    logging.info(f"Task {task.task_id} marked not runnable.")
                    results[str(task_id)] = True
                elif task in self.queued_tasks:
                    # Suspend a queued task
                    self.queued_tasks.remove(task)
                    self.paused_tasks.append(task)
                    task.runnable = False
                    logging.info(f"Queued task {task.task_id} suspended.")
                    results[str(task_id)] = True
                else:
                    logging.error(f"Task {task_id} not found or cannot be suspended.")
                    results[str(task_id)] = False
            else:
                logging.error(f"Task {task_id} not found.")
                results[str(task_id)] = False

        # Schedule tasks to ensure other queued tasks can run
        await self.schedule_tasks()
        return results

    async def resume_tasks(self, task_ids):
        results = {}
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task and task in self.paused_tasks:
                if task.process:
                    # Mark as runnable, let scheduler do the rest
                    task.runnable = True
                    logging.info(f"Task {task.task_id} marked runnable.")
                else:
                    # Task hasn't started yet, move it back to the queue to be started
                    self.queued_tasks.append(task)
                    self.paused_tasks.remove(task)
                    task.runnable = True
                    logging.info(f"Queued task {task.task_id} resumed.")

                results[str(task_id)] = True
            else:
                logging.error(f"Task {task_id} not found or not paused.")
                results[str(task_id)] = False

        # Schedule tasks to ensure resumed tasks are picked up
        await self.schedule_tasks()
        return results

    async def list_tasks(self):
        tasks_info = {
            "max_cpus": self.max_cpus,
            "active": [task.task_id for task in self.active_tasks],
            "queued": [task.task_id for task in self.queued_tasks],
            "paused": [task.task_id for task in self.paused_tasks if not task.runnable],
            "runnable_paused": [task.task_id for task in self.paused_tasks if task.runnable]
        }
        logging.info(f"Listing tasks: {tasks_info}")
        return tasks_info

    async def get_task_info(self, task_id):
        task = self.get_task(task_id)
        if task:
            logging.info(f"Task cmd for {task_id}: {task.command}")
            return task.command
        else:
            logging.error(f"Task {task_id} not found.")
            return None

    async def kill_tasks(self, task_ids, signal_type=signal.SIGTERM):
        logging.info(f'kill_tasks called: {task_ids}')
        results = {}
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task:
                try:
                    # Handle queued tasks that haven't started yet
                    if task in self.queued_tasks:
                        self.queued_tasks.remove(task)
                        logging.info(f"Task {task.task_id} removed from queue.")
                        results[str(task_id)] = True

                    # Handle active or paused tasks
                    elif task in self.active_tasks or task in self.paused_tasks:
                        # Send the termination signal
                        os.kill(task.process.pid, signal_type)
                        task.process = None  # Set process to None to indicate it has been terminated

                        if task in self.active_tasks:
                            self.active_tasks.remove(task)
                        elif task in self.paused_tasks:
                            self.paused_tasks.remove(task)

                        logging.info(f"Task {task.task_id} killed with signal {signal_type}.")
                        results[str(task_id)] = True
                    else:
                        logging.error(f"Task {task.task_id} could not be killed: Not found in active or paused lists.")
                        results[str(task_id)] = False
                except ProcessLookupError:
                    # The process may already be reaped by the time we try to kill it.
                    logging.error(f"Task {task.task_id} could not be killed: Process not found.")
                    results[str(task_id)] = False
            else:
                logging.error(f"Task {task_id} not found.")
                results[str(task_id)] = False
        return results

    def get_task(self, task_id):
        for task in self.active_tasks + self.queued_tasks + self.paused_tasks:
            if task.task_id == task_id:
                return task
        return None

async def handle_rpc(request, task_manager):
    try:
        data = await request.text()

        # Parse the incoming XML-RPC request
        params, method_name = xmlrpc.server.loads(data)

        # Determine the method to call
        if method_name == "submit_task":
            command, user, path, env, log_stdout, log_stderr = params
            task_id = await task_manager.submit_task(command, user, path, env, log_stdout, log_stderr)
            response = xmlrpc.client.dumps((task_id,), methodresponse=True)

        elif method_name == "list_tasks":
            tasks_info = await task_manager.list_tasks()
            response = xmlrpc.client.dumps((tasks_info,), methodresponse=True)

        elif method_name == "id_task":
            task_id = params[0]
            task_info = await task_manager.get_task_info(task_id)
            response = xmlrpc.client.dumps((task_info,), methodresponse=True, allow_none=True)

        elif method_name == "suspend_tasks":
            task_ids = params[0]
            result = await task_manager.suspend_tasks(task_ids)
            response = xmlrpc.client.dumps((result,), methodresponse=True)

        elif method_name == "resume_tasks":
            task_ids = params[0]
            result = await task_manager.resume_tasks(task_ids)
            response = xmlrpc.client.dumps((result,), methodresponse=True)

        elif method_name == "kill_tasks":
            task_ids, signal_type = params
            result = await task_manager.kill_tasks(task_ids, signal_type)
            response = xmlrpc.client.dumps((result,), methodresponse=True)

        elif method_name == "stop_server":
            response = xmlrpc.client.dumps((True,), methodresponse=True)
            logging.info("Shutting down server...")
            asyncio.create_task(graceful_shutdown())

        else:
            response = xmlrpc.client.dumps(
                xmlrpc.client.Fault(1, f"Unknown method '{method_name}'")
            )

        return web.Response(text=response, content_type="text/xml")

    except Exception as e:
        logging.error(f"Error processing request: {e}")
        fault_response = xmlrpc.client.dumps(
            xmlrpc.client.Fault(1, f"Server error: {e}")
        )
        return web.Response(text=fault_response, content_type="text/xml")


SOCKET_PATH = "/tmp/batch_queue.sock"  # Define your UDS path

async def start_server(task_manager):
    # Remove the existing socket file if it exists
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    async def handler(request):
        return await handle_rpc(request, task_manager)

    app = web.Application()
    app.add_routes([web.post('/RPC2', handler)])

    runner = web.AppRunner(app)
    await runner.setup()

    # Create a Unix domain socket
    site = web.UnixSite(runner, SOCKET_PATH)
    await site.start()

    # Restrict permissions to the owner
    os.chmod(SOCKET_PATH, 0o600)

    logging.info(f"Server started on Unix domain socket: {SOCKET_PATH}")

    try:
        await asyncio.Future()  # Run forever
    except asyncio.CancelledError:
        await runner.cleanup()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

async def graceful_shutdown():
    logging.info("Initiating graceful shutdown...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info("Shutdown complete.")
    asyncio.get_event_loop().stop()

def main():
    max_cpus = int(os.getenv("MAX_CPUS", os.cpu_count()))
    task_manager = TaskManager(max_cpus)
    logging.info (f'TaskManager started with {max_cpus} cpus')
    
    try:
        asyncio.run(start_server(task_manager))
    except KeyboardInterrupt:
        logging.info("Server interrupted and shutting down.")


if __name__ == "__main__":
    main()
