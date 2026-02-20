# PLAN: Multiple Dev Task Queues

## Requirements Analysis

### What needs to be built
1. **Modify `add_dev_task`** in `src/iris/functions.py` to accept a `queue_name` parameter that maps to predefined queue files
2. **Add `list_dev_queues()`** function to show available queues and their file paths
3. **Update function description** so Claude understands natural language like "add an urgent dev task" should route to the urgent queue

### Why
- Currently users can only add tasks to a single queue (queue.txt)
- The multiagent-loop supports multiple queues but iris has no way to target them
- Users want to prioritize tasks differently (urgent vs backlog)

### Current State
- `add_dev_task(task, queue_path=None)` exists at `functions.py:314-341`
- Uses `@register` decorator to expose to Claude via system prompt
- Defaults to `~/git/multiagent-loop/queue.txt`

## Implementation Steps

### 1. Define queue mappings (constants)
Add at module level in `functions.py`:
```python
DEV_QUEUES = {
    "default": "queue.txt",
    "urgent": "urgent.txt",
    "backlog": "backlog.txt",
}
DEV_QUEUE_BASE = Path.home() / "git" / "multiagent-loop"
```

### 2. Modify `add_dev_task` function
- Add `queue_name` parameter (default: "default")
- Keep `queue_path` for backwards compatibility but make `queue_name` primary
- If `queue_name` is provided and valid, resolve to the mapped path
- If `queue_name` is unknown, return an error
- Update the `@register` decorator description to include queue names

**Parameter priority:**
1. If `queue_path` is explicitly provided, use it (backwards compat)
2. Otherwise, look up `queue_name` in `DEV_QUEUES`

**Updated function signature:**
```python
def add_dev_task(task, queue_name="default", queue_path=None):
```

**Updated description:**
```
"Add a development task to a multiagent-loop queue. Use queue_name='urgent' for urgent tasks, 'backlog' for low priority, or 'default' for the main queue."
```

### 3. Add `list_dev_queues` function
New registered function:
```python
@register(
    name="list_dev_queues",
    description="List available development task queues and their file paths",
    parameters=[],
)
def list_dev_queues():
    queues = []
    for name, filename in DEV_QUEUES.items():
        path = DEV_QUEUE_BASE / filename
        exists = path.exists()
        count = len(path.read_text().splitlines()) if exists else 0
        queues.append({
            "name": name,
            "path": str(path),
            "exists": exists,
            "task_count": count,
        })
    return {"queues": queues}
```

## Key Design Decisions

1. **Use `queue_name` not `queue_path` as primary API** - Users speak in terms of queue names ("urgent queue"), not file paths. The `queue_path` parameter remains for power users.

2. **Hardcode queue mappings** - The three queues (default, urgent, backlog) are defined in code. This keeps it simple. If users want custom queues, they can use `queue_path`.

3. **Update description for natural language routing** - Claude reads the function description to decide when to call it. The description must mention "urgent" and "backlog" so Claude routes "add an urgent dev task" correctly.

4. **Include task count in list_dev_queues** - Useful for users to see which queues have pending work.

## Success Criteria

When complete, users should be able to:

1. ✅ "Iris, add a dev task: implement feature X" → adds to default queue (queue.txt)
2. ✅ "Iris, add an urgent dev task: fix the login bug" → adds to urgent queue (urgent.txt)
3. ✅ "Iris, add to the backlog: refactor the API" → adds to backlog queue (backlog.txt)
4. ✅ "Iris, what dev queues are available?" → shows all three queues with task counts
5. ✅ "Iris, add dev task to backlog queue: update docs" → explicit queue name works

---

## SELF-REVIEW

### What went well
- Clear existing codebase with good patterns to follow
- The `@register` decorator system makes it straightforward to add/modify functions
- The task requirements are well-defined and achievable

### Missing information
- Are there other queue files already in use? (checked multiagent-loop, found queue.txt is the default)
- Should queues be configurable via a config file? (decision: no, keep it simple)
- Should we validate the queue files exist before writing? (decision: no, create parent dirs if needed like current impl)

### What would make this easier next time
- Having a test file for `functions.py` would help verify the implementation
- Knowing the exact natural language patterns users will use

### Confidence: HIGH

Reasons:
- Simple, well-scoped change to existing code
- Clear patterns to follow in the codebase
- All requirements are concrete and testable
- No external dependencies or complex integrations
- The existing `add_dev_task` function already works; we're just extending it
