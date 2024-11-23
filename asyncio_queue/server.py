#!/usr/bin/env python3

import os
import signal
import logging
import asyncio
import xmlrpc.client
import xmlrpc.server
from aiohttp import web

logging.basicConfig(filename=os.path.expanduser("~/batch_queue.log"), level=logging.INFO)

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
        self.active_tasks.remove(task)

        if task.process.returncode == 0:
            logging.info(f"Task {task.task_id} completed successfully.")
        else:
            logging.error(f"Task {task.task_id} failed with return code {task.process.returncode}.")

        # Schedule any tasks waiting in the queue
        await self.schedule_tasks()

    async def suspend_task(self, task_id):
        task = self.get_task(task_id)
        if task and task in self.active_tasks:
            os.kill(task.process.pid, signal.SIGSTOP)
            self.active_tasks.remove(task)
            task.runnable = False
            self.paused_tasks.append(task)
            logging.info(f"Task {task.task_id} suspended.")
            return True
        else:
            logging.error(f"Task {task_id} not found or not active.")
            return False

    async def resume_task(self, task_id):
        task = self.get_task(task_id)
        if task and task in self.paused_tasks:
            task.runnable = True
            logging.info(f"Task {task.task_id} marked as runnable.")
            await self.schedule_tasks()
            return True
        else:
            logging.error(f"Task {task_id} not found or not paused.")
            return False

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

    async def kill_task(self, task_id, signal_type):
        task = self.get_task(task_id)
        if task:
            try:
                # Handle queued tasks that haven't started yet
                if task in self.queued_tasks:
                    self.queued_tasks.remove(task)
                    logging.info(f"Task {task.task_id} removed from queue.")
                # Handle active or paused tasks
                else:
                    os.kill(task.process.pid, signal_type)
                    if task in self.active_tasks:
                        self.active_tasks.remove(task)
                    elif task in self.paused_tasks:
                        self.paused_tasks.remove(task)
                    logging.info(f"Task {task.task_id} killed with signal {signal_type}.")
                return True
            except ProcessLookupError:
                logging.error(f"Task {task.task_id} could not be killed: Process not found.")
                return False
        else:
            logging.error(f"Task {task_id} not found.")
            return False

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

        elif method_name == "suspend_task":
            task_id = params[0]
            result = await task_manager.suspend_task(task_id)
            response = xmlrpc.client.dumps((result,), methodresponse=True)

        elif method_name == "resume_task":
            task_id = params[0]
            result = await task_manager.resume_task(task_id)
            response = xmlrpc.client.dumps((result,), methodresponse=True)

        elif method_name == "kill_task":
            task_id, signal_type = params
            result = await task_manager.kill_task(task_id, signal_type)
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


async def start_server(task_manager):
    # Use a closure to pass task_manager into the handler
    async def handler(request):
        return await handle_rpc(request, task_manager)

    app = web.Application()
    app.add_routes([web.post('/RPC2', handler)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 7080)
    await site.start()
    logging.info(f"Server started on http://localhost:7080/")

    try:
        await asyncio.Future()  # Run forever
    except asyncio.CancelledError:
        await runner.cleanup()

async def graceful_shutdown():
    logging.info("Initiating graceful shutdown...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    logging.info("Shutdown complete.")
    asyncio.get_event_loop().stop()

def main():
    max_cpus = int(os.getenv("MAX_CPUS", 2))
    task_manager = TaskManager(max_cpus)
    logging.info (f'TaskManager started with {max_cpus} cpus')
    
    try:
        asyncio.run(start_server(task_manager))
    except KeyboardInterrupt:
        logging.info("Server interrupted and shutting down.")


if __name__ == "__main__":
    main()
