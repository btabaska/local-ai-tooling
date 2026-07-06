---
description: Run a consolidated multi-lens code review of the current change
agent: build
subtask: true
---
Engage the **requesting-code-review** skill (or dispatch the @reviewer subagent) on the current diff
(`git diff main...HEAD` unless I say otherwise). Return prioritized findings with severities and
concrete fixes, then a SHIP / SHIP WITH NITS / NEEDS WORK verdict. Do not edit code in this pass.

$ARGUMENTS
