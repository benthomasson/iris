# Usage Instructions

---

## TEST CASES

Created `test_dev_queues.py` with 16 test cases across 3 test classes:

**TestAddDevTask (9 tests)**
- `test_add_task_default_queue` - Adding to default queue works
- `test_add_task_urgent_queue` - Adding to urgent queue works
- `test_add_task_backlog_queue` - Adding to backlog queue works
- `test_add_task_unknown_queue_returns_error` - Unknown queue names return helpful error
- `test_add_task_custom_queue_path` - Custom queue_path works
- `test_queue_path_overrides_queue_name` - queue_path takes priority over queue_name
- `test_backwards_compatibility_no_queue_name` - Old calls with just task work
- `test_task_strip_whitespace` - Task text is trimmed
- `test_multiple_tasks_append` - Tasks append, don't overwrite

**TestListDevQueues (5 tests)**
- `test_list_queues_empty` - Works with no queue files
- `test_list_queues_with_tasks` - Shows correct task counts
- `test_list_queues_returns_all_required_fields` - Has name, filename, path, task_count
- `test_list_queues_correct_file_mapping` - Maps queue names to correct filenames
- `test_list_queues_ignores_blank_lines` - Blank lines not counted as tasks

**TestDevQueuesConstants (2 tests)**
- `test_dev_queues_has_required_keys` - DEV_QUEUES has default, urgent, backlog
- `test_dev_queue_base_is_path` - DEV_QUEUE_BASE is a Path object

---

## USAGE INSTRUCTIONS FOR USER

See `tester/USAGE.md` for full documentation. Summary:

**Natural language examples:**
- "Iris, add a dev task: implement user authentication" → default queue
- "Iris, add an urgent dev task: fix the login bug" → urgent queue
- "Iris, add a backlog dev task: refactor the API layer" → backlog queue
- "Iris, list the dev queues" → shows all queues with task counts

**Direct function calls:**
```python
add_dev_task("task description")                    # default queue
add_dev_task("task", queue_name="urgent")           # urgent queue
add_dev_task("task", queue_name="backlog")          # backlog queue
add_dev_task("task", queue_path="/custom/path.txt") # custom path
list_dev_queues()                                   # list all queues
```

**Verification:**
```bash
cat ~/git/multiagent-loop/queue.txt     # default queue
cat ~/git/multiagent-loop/urgent.txt    # urgent queue
cat ~/git/multiagent-loop/backlog.txt   # backlog queue
```

---

## TEST VERDICT

**TESTS_PASSED**

All 16 tests pass. The implementation correctly:
- Routes tasks to the correct queue file based on queue_name
- Maintains backwards compatibility with existing add_dev_task calls
- Prioritizes queue_path over queue_name when both are provided
- Returns helpful error messages for unknown queue names
- Lists queues with accurate task counts

---

## SELF-REVIEW

**What was easy to test?**
- The function logic was straightforward to unit test with mocking
- Using `tmp_path` fixture made file-based testing clean
- The implementation followed clear patterns that were easy to verify

**What was hard?**
- Testing natural language routing (e.g., "add an urgent dev task") isn't possible at the unit level - that depends on Claude's interpretation of the function description. Real-world validation requires testing with Iris voice/chat.

**What information was missing?**
- The plan was truncated mid-sentence for `list_dev_queues`. Not blocking but slightly inconvenient.
- No existing test patterns in the codebase to follow (had to create from scratch)

**What would make my job easier?**
- Existing test files to model after
- Integration test setup for testing Claude's function routing

**Gaps revealed by testing?**
- None. The implementation is solid. The only untested aspect is whether Claude correctly interprets phrases like "urgent dev task" to use `queue_name="urgent"`, but that's a Claude prompt-engineering concern, not a code bug.

[Committed changes to tester branch]