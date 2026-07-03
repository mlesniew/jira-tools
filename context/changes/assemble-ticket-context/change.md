---
change_id: assemble-ticket-context
title: Polish the assemble-ticket-context skill for standalone end-to-end use
status: implementing
created: 2026-07-02
updated: 2026-07-02
archived_at: null
---

## Notes

Let's polish the ticket context assembling skill.  Let's make sure it can run end-to-end in Claude.  Review the current format of the skill.  Think of ways to improve it so that it's useful for developers.  Make sure the skill can use `jira-tools` by itself, without additional information from CLAUDE.md, other files or the user.  Consider including a check at the beginning to see if jira-tools works and is configured with auth info.  If it isn't, stop.  We'll write a separate script or skill to set it up later.
