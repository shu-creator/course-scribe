"""Validation result schema definitions."""

from enum import Enum
from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    """Severity level of a validation issue."""

    ERROR = "error"  # Must be fixed
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational


class IssueCategory(str, Enum):
    """Category of validation issue."""

    SCOPE_VIOLATION = "scope_violation"  # Content outside syllabus scope
    MISSING_CONTENT = "missing_content"  # Expected content not found
    CALCULATION_ERROR = "calculation_error"  # Math/calculation issue
    CONSISTENCY_ERROR = "consistency_error"  # Internal consistency issue
    FORMAT_ERROR = "format_error"  # Formatting/structure issue


class ValidationIssue(BaseModel):
    """A single validation issue."""

    category: IssueCategory = Field(..., description="Issue category")
    severity: IssueSeverity = Field(..., description="Issue severity")
    message: str = Field(..., min_length=1, description="Issue description")
    location: str = Field(default="", description="Where the issue was found")
    suggestion: str = Field(default="", description="Suggested fix")


class ValidationResult(BaseModel):
    """Complete validation result."""

    is_valid: bool = Field(..., description="Whether validation passed")
    issues: list[ValidationIssue] = Field(
        default_factory=list, description="List of issues found"
    )
    checked_items: list[str] = Field(
        default_factory=list, description="List of items that were checked"
    )
    summary: str = Field(default="", description="Validation summary")

    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues."""
        return any(i.severity == IssueSeverity.WARNING for i in self.issues)

    def error_count(self) -> int:
        """Count error-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    def warning_count(self) -> int:
        """Count warning-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    def to_report(self) -> str:
        """Generate a human-readable validation report."""
        lines = ["# Validation Report", ""]

        status = "PASSED" if self.is_valid else "FAILED"
        lines.append(f"**Status:** {status}")
        lines.append(f"**Errors:** {self.error_count()}")
        lines.append(f"**Warnings:** {self.warning_count()}")
        lines.append("")

        if self.summary:
            lines.append(f"**Summary:** {self.summary}")
            lines.append("")

        if self.issues:
            lines.append("## Issues")
            for issue in self.issues:
                icon = {"error": "[ERROR]", "warning": "[WARN]", "info": "[INFO]"}[
                    issue.severity.value
                ]
                lines.append(f"- {icon} **{issue.category.value}**: {issue.message}")
                if issue.location:
                    lines.append(f"  - Location: {issue.location}")
                if issue.suggestion:
                    lines.append(f"  - Suggestion: {issue.suggestion}")
            lines.append("")

        if self.checked_items:
            lines.append("## Checked Items")
            for item in self.checked_items:
                lines.append(f"- {item}")

        return "\n".join(lines)
