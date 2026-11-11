"""  Tasks Runner

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import time
import os
from threading import Thread
from queue import Queue

class TaskRunner:
    __max_tasks:int = os.cpu_count()
    __queue = Queue()
    __threads = []
    __running = False

    def __init__(self, max_tasks:int = 0):
        if max_tasks > 0:
            self.__max_tasks = max_tasks

    def start(self):
        # Management thread
        Thread(target= self.__loop).start()

    def stop(self):
        self.__running = False

        # We wait for all the threads to terminate
        for task in self.__threads:
            if task is not None:
                task.join()

    def run_task(self, task, args):
        thread = Thread(target= task, args= args)
        self.__queue.put(thread)
        
    def __loop(self):
        self.__running = True

        while self.__running:
            # We start as many threads as max_tasks
            # We join all these threads
            # If there are too many running tasks we enque             
            if self.__queue.qsize() > 0 and len(self.__threads) < self.__max_tasks:
                # We start a new thread
                thread:Thread = self.__queue.get()
                self.__threads.append(thread)
                thread.start()

                print(f"Running threads : {len(self.__threads)}")

            # Then we join oldest thread
            if len(self.__threads) > 0:
                thread = self.__threads.pop(0)
                thread.join()
                
            time.sleep(0.1)