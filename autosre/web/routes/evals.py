"""
Evals Routes - Evaluation scenario management.

Provides:
- List all scenarios with run button
- Results history
- Create new scenario form
- Run scenarios via HTMX
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from autosre.evals import (
    list_scenarios,
    load_scenario,
    run_scenario,
    get_results,
    get_all_scenarios,
)


router = APIRouter()


def get_templates(request: Request):
    """Get templates from app state."""
    return request.app.state.templates


# In-memory store for running scenarios (would use Redis/DB in production)
_running_scenarios: dict[str, dict] = {}


@router.get("/", response_class=HTMLResponse)
async def evals_page(request: Request):
    """Main evals page."""
    templates = get_templates(request)
    
    scenarios = list_scenarios()
    results = get_results(limit=20)
    
    # Calculate summary stats
    total_runs = len(results)
    passed = sum(1 for r in results if r.get("success"))
    avg_accuracy = sum(r.get("accuracy", 0) for r in results) / max(total_runs, 1)
    
    summary = {
        "total_runs": total_runs,
        "passed": passed,
        "failed": total_runs - passed,
        "pass_rate": (passed / total_runs * 100) if total_runs > 0 else 0,
        "avg_accuracy": avg_accuracy * 100,
    }
    
    return templates.TemplateResponse(
            request=request,
            name="evals.html",
            context={"scenarios": scenarios,
            "results": results[:10],
            "summary": summary}
        )


@router.get("/list", response_class=HTMLResponse)
async def scenario_list(request: Request):
    """HTMX endpoint for scenario list."""
    templates = get_templates(request)
    scenarios = list_scenarios()
    
    return templates.TemplateResponse(
            request=request,
            name="partials/scenario_list.html",
            context={"scenarios": scenarios}
        )


@router.get("/results", response_class=HTMLResponse)
async def results_list(request: Request, scenario: Optional[str] = None, limit: int = 20):
    """HTMX endpoint for results list."""
    templates = get_templates(request)
    results = get_results(scenario=scenario, limit=limit)
    
    return templates.TemplateResponse(
            request=request,
            name="partials/results_list.html",
            context={"results": results}
        )


@router.post("/run/{scenario_name}", response_class=HTMLResponse)
async def run_scenario_endpoint(
    request: Request,
    scenario_name: str,
    background_tasks: BackgroundTasks,
):
    """Run a scenario (HTMX endpoint)."""
    templates = get_templates(request)
    
    # Verify scenario exists
    scenario = load_scenario(scenario_name)
    if not scenario:
        return templates.TemplateResponse(
            "partials/scenario_error.html",
            {
                "request": request,
                "error": f"Scenario '{scenario_name}' not found",
            }
        )
    
    # Create run ID
    run_id = f"{scenario_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    # Store running state
    _running_scenarios[run_id] = {
        "scenario": scenario_name,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
    }
    
    # Run in background
    async def run_and_store():
        try:
            result = await run_scenario(scenario_name)
            _running_scenarios[run_id]["status"] = "complete"
            _running_scenarios[run_id]["result"] = result
        except Exception as e:
            _running_scenarios[run_id]["status"] = "failed"
            _running_scenarios[run_id]["error"] = str(e)
    
    background_tasks.add_task(asyncio.create_task, run_and_store())
    
    return templates.TemplateResponse(
            request=request,
            name="partials/scenario_running.html",
            context={"run_id": run_id,
            "scenario_name": scenario_name}
        )


@router.get("/run/{run_id}/status", response_class=HTMLResponse)
async def run_status(request: Request, run_id: str):
    """Check status of a running scenario (HTMX polling)."""
    templates = get_templates(request)
    
    run_info = _running_scenarios.get(run_id)
    if not run_info:
        return templates.TemplateResponse(
            request=request,
            name="partials/scenario_error.html",
            context={"error": "Run not found"}
        )
    
    if run_info["status"] == "running":
        return templates.TemplateResponse(
            request=request,
            name="partials/scenario_running.html",
            context={"run_id": run_id,
                "scenario_name": run_info["scenario"]}
        )
    elif run_info["status"] == "complete":
        return templates.TemplateResponse(
            request=request,
            name="partials/scenario_result.html",
            context={"result": run_info["result"],
                "scenario_name": run_info["scenario"]}
        )
    else:
        return templates.TemplateResponse(
            request=request,
            name="partials/scenario_error.html",
            context={"error": run_info.get("error", "Unknown error")}
        )


@router.get("/scenario/{scenario_name}", response_class=HTMLResponse)
async def scenario_detail(request: Request, scenario_name: str):
    """View scenario details."""
    templates = get_templates(request)
    
    scenario = load_scenario(scenario_name)
    if not scenario:
        return templates.TemplateResponse(
            "partials/scenario_error.html",
            {"request": request, "error": f"Scenario '{scenario_name}' not found"}
        )
    
    # Get results for this scenario
    results = get_results(scenario=scenario_name, limit=10)
    
    return templates.TemplateResponse(
            request=request,
            name="partials/scenario_detail.html",
            context={"scenario": scenario,
            "results": results}
        )


class ScenarioCreate(BaseModel):
    """Scenario creation model."""
    name: str
    description: str
    difficulty: str = "medium"
    expected_root_cause: str
    expected_service: Optional[str] = None


@router.post("/create", response_class=HTMLResponse)
async def create_scenario(
    request: Request,
    name: str = Form(...),
    description: str = Form(...),
    difficulty: str = Form("medium"),
    expected_root_cause: str = Form(...),
    expected_service: Optional[str] = Form(None),
):
    """Create a new scenario (form submission)."""
    templates = get_templates(request)
    
    # TODO: Actually create the scenario file
    # For now, return success message
    
    return templates.TemplateResponse(
        "partials/scenario_created.html",
        {
            "request": request,
            "name": name,
            "message": f"Scenario '{name}' created successfully",
        }
    )


@router.get("/api/scenarios")
async def api_list_scenarios():
    """API endpoint for listing scenarios."""
    return {"scenarios": list_scenarios()}


@router.get("/api/results")
async def api_list_results(scenario: Optional[str] = None, limit: int = 20):
    """API endpoint for listing results."""
    return {"results": get_results(scenario=scenario, limit=limit)}
