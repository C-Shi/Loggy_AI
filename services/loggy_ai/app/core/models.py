from pydantic import BaseModel, Field


class ActionPlan(BaseModel):
    """One remediation step in an incident action plan."""

    step: int = Field(description="step number starting from 1")
    action: str = Field(description="Immediate step to resolve the issue.")
    warning: str = Field(description="Anything you would be extra cautious about")


class LogAnalysisResponse(BaseModel):
    """Structured analysis for a single consolidated incident."""

    operational_summary: str = Field(
        description="1-sentence summary of what happens, resources are involved, and the severity"
    )
    service_name: str | None = Field(
        description="If present in log, the name of the service that this incident is related to"
    )
    severity: str = Field(
        description=(
            "1 sentence describing how severe this incident's impact is from a business perspective. "
            "Use severity exactly one of: LOW, MEDIUM, HIGH, CRITICAL. "
            "Base this on business impact (revenue, availability, data integrity, compliance), "
            "not log level alone."
        )
    )
    repetitive_issue: bool = Field(description="if this issue has arise multiple time")
    root_cause: str = Field(
        description="Describe if this is a user error or DevOps error or root code error"
    )
    ai_suggestion: str = Field(
        description="Your though about this error and where you would start"
    )
    first_seen_timestamp: str = Field(
        description="ISO 8601 timestamp of earliest matching log entry."
    )
    last_seen_timestamp: str = Field(
        description="ISO 8601 timestamp of latest matching log entry."
    )
    action_plan: list[ActionPlan] = Field(
        description="A list of remediation steps to resolve the issue."
    )


class LogAnalysisReport(BaseModel):
    """Top-level response: one or more deduplicated incidents."""

    incidents: list[LogAnalysisResponse]


class ValidationResult(BaseModel):
    """Result of instruction validation."""

    is_safe: bool = Field(description="Whether the instruction is safe to use")
    reason: str = Field(description="Reasoning for the safety decision")
    refined_instruction: str = Field(description="The cleaned instruction if safe")
