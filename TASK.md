# Task

Add support for multiple multiagent-loop queues to iris. Modify add_dev_task to accept a queue_name parameter that maps to different queue files. Add a new function list_dev_queues() that shows available queues. Default queues should include 'default' (queue.txt), 'urgent' (urgent.txt), and 'backlog' (backlog.txt). Users should be able to say 'Iris, add an urgent dev task: fix the login bug' to add to the urgent queue.

Started: 2026-02-20T11:08:37.893381