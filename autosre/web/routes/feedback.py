"""
Feedback Routes - Submit and view feedback.

Provides:
- Submit feedback on agent analyses
- View feedback history
- Export feedback for fine-tuning
"""

from datetime import datetime, timezone
from typing import Optional
import json

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse

from autosre.feedback import FeedbackStore, Feedback


router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def feedback_page(request: Request):
    """Main feedback page."""
    templates = get_templates(request)
    
    try:
        store = FeedbackStore()
        recent_feedback = store.get_recent(limit=20)
        stats = store.get_stats()
    except Exception:
        # Feedback store might not be initialized
        recent_feedback = []
        stats = {"total": 0, "positive": 0, "negative": 0}
    
    return templates.TemplateResponse(
            request=request,
            name="feedback.html",
            context={"recent_feedback": recent_feedback,
            "stats": stats}
        )


@router.post("/submit", response_class=HTMLResponse)
async def submit_feedback(
    request: Request,
    incident_id: str = Form(...),
    rating: str = Form(...),  # "positive", "negative", "neutral"
    category: str = Form("general"),
    comment: Optional[str] = Form(None),
    correct_root_cause: Optional[str] = Form(None),
    correct_action: Optional[str] = Form(None),
):
    """Submit feedback on an analysis."""
    templates = get_templates(request)
    
    try:
        store = FeedbackStore()
        
        feedback = Feedback(
            incident_id=incident_id,
            rating=rating,
            category=category,
            comment=comment,
            correct_root_cause=correct_root_cause,
            correct_action=correct_action,
            submitted_at=datetime.now(timezone.utc),
        )
        
        store.add(feedback)
        
        return templates.TemplateResponse(
            request=request,
            name="partials/feedback_success.html",
            context={"message": "Feedback submitted successfully"}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/feedback_error.html",
            {
                "request": request,
                "error": f"Failed to submit feedback: {str(e)}",
            }
        )


@router.get("/form/{incident_id}", response_class=HTMLResponse)
async def feedback_form(request: Request, incident_id: str):
    """Get feedback form for an incident (HTMX)."""
    templates = get_templates(request)
    
    return templates.TemplateResponse(
            request=request,
            name="partials/feedback_form.html",
            context={"incident_id": incident_id}
        )


@router.get("/history", response_class=HTMLResponse)
async def feedback_history(
    request: Request,
    limit: int = 50,
    rating: Optional[str] = None,
):
    """HTMX endpoint for feedback history."""
    templates = get_templates(request)
    
    try:
        store = FeedbackStore()
        feedback_list = store.get_recent(limit=limit)
        
        if rating:
            feedback_list = [f for f in feedback_list if f.rating == rating]
    except Exception:
        feedback_list = []
    
    return templates.TemplateResponse(
            request=request,
            name="partials/feedback_history.html",
            context={"feedback_list": feedback_list}
        )


@router.get("/export")
async def export_feedback(format: str = "json"):
    """Export feedback for fine-tuning."""
    try:
        store = FeedbackStore()
        feedback_list = store.get_all()
        
        if format == "jsonl":
            # JSONL format for fine-tuning
            lines = []
            for fb in feedback_list:
                lines.append(json.dumps(fb.model_dump(), default=str))
            content = "\n".join(lines)
            return JSONResponse(
                content={"data": content},
                media_type="application/jsonl",
            )
        else:
            return {"feedback": [fb.model_dump() for fb in feedback_list]}
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def feedback_stats():
    """Get feedback statistics."""
    try:
        store = FeedbackStore()
        return store.get_stats()
    except Exception as e:
        return {"error": str(e)}
