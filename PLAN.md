# Plan

Task: Add support for multiple multiagent-loop queues to iris. Modify add_dev_task to accept a queue_name parameter that maps to different queue files. Add a new function list_dev_queues() that shows available queues. Default queues should include 'default' (queue.txt), 'urgent' (urgent.txt), and 'backlog' (backlog.txt). Users should be able to say 'Iris, add an urgent dev task: fix the login bug' to add to the urgent queue.

Plan written to `/Users/ben/git/multiagent-loop/workspaces/iris/planner/PLAN.md`.

## Summary

**Task:** Add multiple queue support to iris's dev task functionality

**Key Changes:**
1. Add `DEV_QUEUES` mapping: default→queue.txt, urgent→urgent.txt, backlog→backlog.txt
2. Modify `add_dev_task` to accept `queue_name` parameter (default: "default") alongside existing `queue_path`
3. Add new `list_dev_queues()` function showing available queues with task counts
4. Update function description so Claude routes "urgent dev task" to the urgent queue

**Files to modify:** `src/iris/functions.py` (lines 311-341, plus new function)

**Confidence:** HIGH - straightforward extension of existing patterns in a well-structured codebase.

[Committed changes to planner branch]