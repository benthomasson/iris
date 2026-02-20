# Usage Instructions: Multiple Dev Task Queues

## Overview

Iris now supports multiple development task queues for the multiagent-loop. You can add tasks to different queues based on priority:

| Queue | Filename | Purpose |
|-------|----------|---------|
| `default` | queue.txt | Main queue for standard tasks |
| `urgent` | urgent.txt | High-priority tasks that need immediate attention |
| `backlog` | backlog.txt | Low-priority tasks for later |

All queue files are stored in `~/git/multiagent-loop/`.

## Adding Tasks

### Natural Language (Voice or Chat)

Simply tell Iris which queue you want:

```
"Iris, add a dev task: implement user authentication"
→ Added to default queue (queue.txt)

"Iris, add an urgent dev task: fix the login bug"
→ Added to urgent queue (urgent.txt)

"Iris, add a backlog dev task: refactor the API layer"
→ Added to backlog queue (backlog.txt)
```

### Direct Function Calls

If calling the function directly:

```python
# Add to default queue
add_dev_task("implement user authentication")

# Add to urgent queue
add_dev_task("fix the login bug", queue_name="urgent")

# Add to backlog queue
add_dev_task("refactor the API layer", queue_name="backlog")

# Custom queue path (overrides queue_name)
add_dev_task("special task", queue_path="/path/to/custom/queue.txt")
```

## Expected Output

### add_dev_task

Success response:
```json
{
  "status": "added",
  "task": "fix the login bug",
  "queue_name": "urgent",
  "queue_path": "/Users/you/git/multiagent-loop/urgent.txt"
}
```

Error response (unknown queue):
```json
{
  "error": "Unknown queue name: 'invalid'. Available queues: default, urgent, backlog"
}
```

### list_dev_queues

Query: "Iris, show me the dev task queues" or "Iris, list dev queues"

Response:
```json
{
  "queues": [
    {
      "name": "default",
      "filename": "queue.txt",
      "path": "/Users/you/git/multiagent-loop/queue.txt",
      "task_count": 5
    },
    {
      "name": "urgent",
      "filename": "urgent.txt",
      "path": "/Users/you/git/multiagent-loop/urgent.txt",
      "task_count": 2
    },
    {
      "name": "backlog",
      "filename": "backlog.txt",
      "path": "/Users/you/git/multiagent-loop/backlog.txt",
      "task_count": 10
    }
  ]
}
```

## Verification

To verify the feature is working:

1. **Add a task to each queue:**
   ```
   "Iris, add a dev task: test default queue"
   "Iris, add an urgent dev task: test urgent queue"
   "Iris, add a backlog dev task: test backlog queue"
   ```

2. **List the queues to confirm:**
   ```
   "Iris, list the dev queues"
   ```
   You should see task_count = 1 for each queue.

3. **Check the files directly:**
   ```bash
   cat ~/git/multiagent-loop/queue.txt
   cat ~/git/multiagent-loop/urgent.txt
   cat ~/git/multiagent-loop/backlog.txt
   ```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown queue name: 'xyz'` | Invalid queue_name parameter | Use 'default', 'urgent', or 'backlog' |
| Task not appearing | Task may have been added to wrong queue | Use `list_dev_queues()` to check counts |
| Permission denied | Cannot write to queue directory | Ensure `~/git/multiagent-loop/` exists and is writable |

## Backwards Compatibility

Existing integrations that call `add_dev_task(task)` or `add_dev_task(task, queue_path="/custom/path")` continue to work unchanged. The new `queue_name` parameter is optional and defaults to "default".

## Running Tests

To run the test suite:

```bash
cd /Users/ben/git/multiagent-loop/workspaces/iris
uv run pytest tester/test_dev_queues.py -v
```

All 16 tests should pass.
