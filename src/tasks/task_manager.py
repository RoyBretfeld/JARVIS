import json
import os
import uuid
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages tasks stored in a JSON file."""

    def __init__(self, filepath="data/tasks.json"):
        """
        Initializes the TaskManager.

        Args:
            filepath (str): The path to the JSON file where tasks are stored.
                              Defaults to "data/tasks.json".
        """
        self.filepath = filepath
        self.tasks = []
        self._ensure_data_dir_exists()
        self.load_tasks()

    def _ensure_data_dir_exists(self):
        """Ensures the directory for the tasks file exists."""
        dir_path = os.path.dirname(self.filepath)
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
                logger.info(f"Created directory: {dir_path}")
            except OSError as e:
                logger.error(f"Error creating directory {dir_path}: {e}")

    def load_tasks(self):
        """Loads tasks from the JSON file."""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
                    logger.info(f"Loaded {len(self.tasks)} tasks from {self.filepath}")
            else:
                self.tasks = []
                logger.info(f"Task file {self.filepath} not found. Starting with empty task list.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.filepath}. Starting with empty task list.")
            self.tasks = []
        except Exception as e:
            logger.error(f"Error loading tasks from {self.filepath}: {e}")
            self.tasks = [] # Ensure tasks is a list even on error

    def save_tasks(self):
        """Saves the current list of tasks to the JSON file."""
        self._ensure_data_dir_exists() # Make sure dir exists before saving
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=4, ensure_ascii=False)
            # logger.debug(f"Tasks successfully saved to {self.filepath}") # Maybe too verbose
        except Exception as e:
            logger.error(f"Error saving tasks to {self.filepath}: {e}")

    def add_task(self, description: str) -> dict:
        """
        Adds a new task to the list.

        Args:
            description (str): The description of the task.

        Returns:
            dict: The newly created task.
        """
        if not description or not isinstance(description, str):
            logger.warning("Attempted to add task with invalid description.")
            # Optionally raise an error or return None
            return None

        new_task = {
            "id": str(uuid.uuid4()), # Unique ID for each task
            "description": description,
            "status": "open", # Possible statuses: 'open', 'done'
            "created_at": datetime.now().isoformat()
            # Add more fields later if needed, e.g., 'due_date', 'priority'
        }
        self.tasks.append(new_task)
        self.save_tasks()
        logger.info(f"Added new task: '{description[:50]}...' (ID: {new_task['id']})")
        return new_task

    def list_tasks(self, status_filter="open") -> list:
        """
        Lists tasks, optionally filtering by status.

        Args:
            status_filter (str, optional): Filter tasks by status ('open', 'done', or 'all').
                                           Defaults to "open".

        Returns:
            list: A list of task dictionaries matching the filter.
        """
        if status_filter == "all":
            return self.tasks
        elif status_filter in ["open", "done"]:
            return [task for task in self.tasks if task.get("status") == status_filter]
        else:
            logger.warning(f"Invalid status filter: {status_filter}. Returning open tasks.")
            return [task for task in self.tasks if task.get("status") == "open"]

    def mark_task_done(self, task_id: str) -> bool:
        """
        Marks a specific task as done.

        Args:
            task_id (str): The unique ID of the task to mark as done.

        Returns:
            bool: True if the task was found and marked as done, False otherwise.
        """
        task_found = False
        for task in self.tasks:
            if task.get("id") == task_id:
                if task.get("status") == "done":
                    logger.info(f"Task {task_id} is already marked as done.")
                    task_found = True # Still counts as found
                    # No change needed, don't save
                    return True # Indicate success as it's already in the desired state

                task["status"] = "done"
                task["completed_at"] = datetime.now().isoformat() # Add completion timestamp
                task_found = True
                logger.info(f"Marked task '{task.get('description', 'N/A')[:50]}...' (ID: {task_id}) as done.")
                break # Stop searching once found

        if task_found:
            self.save_tasks()
            return True
        else:
            logger.warning(f"Task with ID {task_id} not found to mark as done.")
            return False

    def remove_task(self, task_id: str) -> bool:
        """
        Removes a task from the list entirely.

        Args:
            task_id (str): The unique ID of the task to remove.

        Returns:
            bool: True if the task was found and removed, False otherwise.
        """
        initial_length = len(self.tasks)
        self.tasks = [task for task in self.tasks if task.get("id") != task_id]
        task_removed = len(self.tasks) < initial_length

        if task_removed:
            self.save_tasks()
            logger.info(f"Removed task with ID: {task_id}")
            return True
        else:
            logger.warning(f"Task with ID {task_id} not found for removal.")
            return False

    def get_task_by_id(self, task_id: str) -> Optional[dict]:
        """
        Retrieves a specific task by its ID.

        Args:
            task_id (str): The unique ID of the task.

        Returns:
            Optional[dict]: The task dictionary if found, otherwise None.
        """
        for task in self.tasks:
            if task.get("id") == task_id:
                return task
        logger.debug(f"Task with ID {task_id} not found.")
        return None

# Example usage (optional, for testing)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # Ensure the data directory exists for the example
    if not os.path.exists("data"):
        os.makedirs("data")
        
    task_manager = TaskManager()

    # Add some tasks
    task1 = task_manager.add_task("Erste Aufgabe erstellen")
    task2 = task_manager.add_task("Zweite Aufgabe hinzufügen")
    task3 = task_manager.add_task("Instagram Post Idee generieren")

    # List open tasks
    print("\nOffene Aufgaben:")
    open_tasks = task_manager.list_tasks()
    for task in open_tasks:
        print(f"- ID: {task['id']}, Beschreibung: {task['description']}")

    # Mark one task as done
    if task1:
        print(f"\nMarkiere Aufgabe {task1['id']} als erledigt...")
        task_manager.mark_task_done(task1['id'])

    # List all tasks
    print("\nAlle Aufgaben:")
    all_tasks = task_manager.list_tasks(status_filter="all")
    for task in all_tasks:
        print(f"- ID: {task['id']}, Status: {task['status']}, Beschreibung: {task['description']}")

    # Remove a task
    if task2:
        print(f"\nEntferne Aufgabe {task2['id']}...")
        task_manager.remove_task(task2['id'])

    # List open tasks again
    print("\nOffene Aufgaben (nach Erledigen/Entfernen):")
    open_tasks_after = task_manager.list_tasks()
    if open_tasks_after:
        for task in open_tasks_after:
            print(f"- ID: {task['id']}, Beschreibung: {task['description']}")
    else:
        print("Keine offenen Aufgaben mehr.") 