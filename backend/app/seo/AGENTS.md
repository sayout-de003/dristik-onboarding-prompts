# SEO agent instructions and tool portability

This guide defines portable expectations for the SEO skill bundle. It is not a grant of tool permissions: each runtime must enforce its own allowlist, user approval rules, and sandbox boundaries.

## Supported agent harnesses

The skill instructions should remain readable and actionable in Cursor, Gemini CLI, Codex, Cline, Aider, and Antigravity. When a harness does not expose a capability, the agent must state the limitation rather than silently pretending the action ran.

## Canonical tool-operation mapping

| Operation | Codex | Cline | Aider | Portable fallback |
| --- | --- | --- | --- | --- |
| Read a file | Read / file inspection | Read File | repository context | use the repository's documented file-reading mechanism |
| Write a new file | Write / patch | Write File | apply patch | emit a reviewable patch |
| Edit an existing file | Edit / patch | Edit File | apply patch | emit a minimal diff |
| Run a command | Bash / terminal | Command | terminal | show the exact command and its result |
| Retrieve a web resource | WebFetch when available | browser / fetch tool | external lookup when configured | cite the URL and disclose when retrieval is unavailable |

Do not claim a read, write, command, or web request succeeded unless the runtime reports success. Never expose secrets in command output or logs.

## Portability validation

Run `python scripts/portability_check.py` from this SEO bundle's root when changing skill frontmatter, agent instructions, script references, or harness-specific tool names. A passing portability check does not replace application tests or evidence verification.

## Evidence and audit rules

- Distinguish directly observed evidence from inference, external measurements, and simulation.
- Missing integrations and failed requests remain unavailable; they are not zero-valued measurements.
- Remediation is not verification. Re-crawl or independently check a change before describing it as fixed and verified.
- Keep changes scoped, testable, and reviewable. Do not remove existing capabilities without explicit approval.
