# Implementation: Multiple Dev Task Queues

## Changes Made

### File Modified: `src/iris/functions.py`

#### 1. Added Queue Constants (lines 160-166)
```python
DEV_QUEUE_BASE = Path.home() / "git" / "multiagent-loop"
DEV_QUEUES = {
    "default": "queue.txt",
    "urgent": "urgent.txt",
    "backlog": "backlog.txt",
}
```

#### 2. Modified `add_dev_task` function (lines 322-356)
- Added `queue_name` parameter (default: "default")
- Kept `queue_path` for backwards compatibility
- Priority: `queue_path` (if provided) > `queue_name` lookup
- Returns clear error for unknown queue names
- Updated description to guide Claude on queue routing

**Signature change:**
```python
# Before
def add_dev_task(task, queue_path=None)

# After
def add_dev_task(task, queue_name="default", queue_path=None)
```

#### 3. Added `list_dev_queues` function (lines 359-379)
- No parameters required
- Returns list of available queues with:
  - `name`: Queue identifier
  - `filename`: The queue file name
  - `path`: Full path to queue file
  - `task_count`: Number of tasks currently in queue

## Usage Examples

**Add to urgent queue:**
"Iris, add an urgent dev task: fix the login bug"
→ Claude calls `add_dev_task(task="fix the login bug", queue_name="urgent")`

**Add to backlog:**
"Iris, add a backlog dev task: refactor the API layer"
→ Claude calls `add_dev_task(task="refactor the API layer", queue_name="backlog")`

**List queues:**
"Iris, show me the dev task queues"
→ Claude calls `list_dev_queues()`

## Backwards Compatibility
- Existing calls with only `task` argument continue to work (defaults to "default" queue)
- Explicit `queue_path` still works and takes priority over `queue_name`
