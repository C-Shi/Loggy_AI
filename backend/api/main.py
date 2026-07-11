import base64
import json
import logging
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google.genai import errors as genai_errors
from models import ConfigItem, MessagePublishedData

from service import LoggyAI
from service.helper.error import LogPayloadLimitError, PromptValidationError

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


@app.get("/health")
def health():
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/run")
def run(config: ConfigItem):
    """Fetch logs from the configured provider and return AI analysis."""
    log_analyzer = LoggyAI.create(config.provider)
    if config.start:
        start_time = datetime.strptime(config.start, "%Y-%m-%d %H:%M:%S")
    else:
        start_time = datetime.now() - timedelta(days=1)

    if config.end:
        end_time = datetime.strptime(config.end, "%Y-%m-%d %H:%M:%S")
    else:
        end_time = datetime.now()

    logs = log_analyzer.fetch_logs(
        limit=config.limit,
        log_name=config.log,
        severity_level=config.severity,
        keywords=config.keywords,
        start_time=start_time,
        end_time=end_time,
    )

    try:
        response = log_analyzer.analyze(logs)
        return response
    except (PromptValidationError, LogPayloadLimitError) as e:
        raise HTTPException(400, detail=e.message)


@app.post("/trigger")
def trigger(payload: MessagePublishedData):
    """
    Analyze a single log entry pushed via Pub/Sub and persist the report to Firestore.

    Uses an atomic signature claim so only one request per error signature calls Gemini.
    """
    logger.info(f"Received CloudEvent Data: {json.dumps(payload.model_dump())}")

    encoded_log = payload.message.data

    decoded_log = base64.b64decode(encoded_log).decode("utf-8")
    log_entry = json.loads(decoded_log)

    log_analyzer = LoggyAI.create(provider=ConfigItem().provider)

    if log_analyzer.has_processed(log_entry):
        return {"status": "ok", "message": "Log has already been processed"}

    claim = log_analyzer.claim_or_follow_signature(log_entry)

    if claim.outcome == "followed_pending":
        raise HTTPException(
            status_code=503,
            detail="Signature analysis in progress; retry shortly",
        )

    if claim.outcome == "followed_ready":
        if not claim.report_id:
            raise HTTPException(
                status_code=500,
                detail="Signature is ready but report_id is missing",
            )
        log_analyzer.record_signature_follower(
            claim.signature, claim.report_id, source_log=log_entry
        )
        log_analyzer.save_processed_event(log_entry, "COMPLETED")
        return {"status": "ok", "message": "Signature follower recorded"}

    # claimed — this request owns Gemini for this signature
    try:
        response = log_analyzer.analyze([log_entry])
        if not response.incidents:
            log_analyzer.release_signature_claim(claim.signature)
            log_analyzer.save_processed_event(log_entry, "COMPLETED")
            return {"status": "ok", "message": "No incidents detected"}

        log_analyzer.finalize_signature_report(
            claim.signature, response.incidents[0], source_log=log_entry
        )
        log_analyzer.save_processed_event(log_entry, "COMPLETED")
        return {"status": "ok"}
    except (PromptValidationError, LogPayloadLimitError) as e:
        log_analyzer.release_signature_claim(claim.signature)
        log_analyzer.save_processed_event(log_entry, "FAILED")
        raise HTTPException(400, detail=e.message)
    except (genai_errors.ClientError, Exception) as e:
        logger.exception("Gemini/analysis failed after signature claim; releasing claim")
        log_analyzer.release_signature_claim(claim.signature)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed; claim released for retry: {e}",
        )
