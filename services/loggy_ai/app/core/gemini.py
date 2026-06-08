from google import genai
import json
from pydantic import BaseModel, Field


class ActionPlan(BaseModel):
    step: int = Field(description="step number starting from 1")
    action: str = Field(description="Immediate step to resolve the issue.")
    warning: str = Field(description="Anything you would be extra cautious about")


class LogAnalysisResponse(BaseModel):
    operational_summary: str = Field(
        description="A 1-sentence executive summary of what happens, what resources are involved, and the serverity"
    )
    root_cause: str = Field(
        description="Describe if this is a user error or DevOps error or root code error"
    )
    ai_suggestion: str = Field(
        description="Your though about this error and where you would start"
    )
    action_plan: list[ActionPlan]


class LogAnalysisReport(BaseModel):
    incidents: list[LogAnalysisResponse]


class GeminiLogAnalyzer:
    def __init__(self, model_name: str = None) -> None:
        self.model_name = model_name
        self.client = genai.Client()

        self.PERSONA = """
            You are a Staff Site Reliability Engineer (SRE) reviewing a stream of production Google Cloud Platform logs in JSON format. 
        """

        self.CONTEXT = """
            These logs are from Google Cloud Platform Cloud Logging. It can be a single incident, or a list of incident. If a single incident, perform analysis. If a list of incident, you should first analyze the entire log, group the same incidents, and for per incident, perform analysis.
        """

    def analyze_logs(self, logs: list) -> LogAnalysisReport:
        config = genai.types.GenerateContentConfig(
            system_instruction=self.PERSONA,
            response_schema=LogAnalysisReport,
            temperature=0,
        )

        minified_logs = self.minified_log(logs)
        response = self.client.models.generate_content(
            model="gemini-3.1-flash-lite",
            config=config,
            contents=[
                genai.types.Part.from_text(text=self.CONTEXT),
                genai.types.Part.from_bytes(
                    data=minified_logs, mime_type="application/json"
                ),
                "Output your response in JSON string format",
            ],
        )
        return response

    def minified_log(self, logs: list):
        minified_json = json.dumps(logs, separators=(",", ":"))

        minified_bytes = minified_json.encode("utf-8")
        return minified_bytes
