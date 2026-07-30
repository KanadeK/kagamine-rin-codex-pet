from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    location: str = ""

    def to_dict(self) -> dict[str, str]:
        value = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.location:
            value["location"] = self.location
        return value


@dataclass
class ValidationReport:
    source: Path
    issues: list[Issue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def is_ok(self, *, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)

    def add(self, severity: str, code: str, message: str, location: str = "") -> None:
        self.issues.append(Issue(severity, code, message, location))

    def to_dict(self, *, strict: bool = False) -> dict[str, Any]:
        return {
            "ok": self.is_ok(strict=strict),
            "strict": strict,
            "source": str(self.source),
            "errorCount": len(self.errors),
            "warningCount": len(self.warnings),
            "issues": [issue.to_dict() for issue in self.issues],
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class InstallResult:
    action: str
    target: Path
    backup: Path | None
    dry_run: bool
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "action": self.action,
            "target": str(self.target),
            "backup": str(self.backup) if self.backup else None,
            "dryRun": self.dry_run,
            "sha256": self.sha256,
        }
