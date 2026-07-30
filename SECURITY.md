# Security policy

## Supported versions

Security fixes are applied to the latest tagged release.

## Reporting

Please use GitHub's private vulnerability reporting for path traversal,
unsafe archive extraction, arbitrary file overwrite, lock bypass, or data
leak issues. Do not include real Codex session contents in a public issue.

## Privacy model

The trace parser runs locally and never performs network requests. Its output
contains only normalized event kinds, state names, source line numbers,
relative timing, and an input SHA-256. Message text, prompts, tool arguments,
tool output, file paths, and account data are intentionally discarded.

Archive installation is also fail-closed: members are validated before the
destination is created, and path traversal, absolute/drive paths, duplicate or
case-colliding names, encryption, symlinks, special files, excessive member
counts, and excessive decompressed sizes are rejected.
