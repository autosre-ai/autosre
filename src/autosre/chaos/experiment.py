"""
Chaos Experiment Runner.

Orchestrates the execution of chaos experiments.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import UUID

from autosre.utils.logging import get_logger

from .models import (
    Experiment,
    ExperimentStatus,
    ExperimentResult,
    Fault,
    FaultType,
    SteadyStateHypothesis,
)

logger = get_logger(__name__)


# Type for steady state probes
SteadyStateProbe = Callable[[SteadyStateHypothesis], Awaitable[bool]]


class ExperimentRunner:
    """
    Runs chaos experiments.
    
    Features:
    - Steady state validation
    - Fault injection coordination
    - Auto-rollback on failure
    - Progress tracking
    - Result collection
    
    Example:
        runner = ExperimentRunner(k8s_client)
        
        experiment = Experiment(
            name="api-latency-test",
            faults=[
                Fault(
                    type=FaultType.NETWORK_LATENCY,
                    target=Target(type=TargetType.DEPLOYMENT, name="api"),
                    parameters={"latency": "200ms"},
                )
            ],
            steady_state=[
                SteadyStateHypothesis(
                    name="API responds",
                    probe_type="http",
                    endpoint="http://api/health",
                    expected_status=200,
                )
            ],
        )
        
        result = await runner.run(experiment)
    """
    
    def __init__(
        self,
        k8s_client: Any,
        fault_injector: Any | None = None,
    ):
        self._k8s = k8s_client
        self._fault_injector = fault_injector
        
        # Active experiments
        self._active: dict[UUID, Experiment] = {}
        
        # History
        self._history: list[Experiment] = []
        
        # Custom probes
        self._probes: dict[str, SteadyStateProbe] = {}
        
        # Built-in probes
        self._register_builtin_probes()
    
    def _register_builtin_probes(self) -> None:
        """Register built-in steady state probes."""
        self._probes["http"] = self._http_probe
        self._probes["tcp"] = self._tcp_probe
        self._probes["prometheus"] = self._prometheus_probe
        self._probes["command"] = self._command_probe
    
    def register_probe(
        self,
        probe_type: str,
        probe: SteadyStateProbe,
    ) -> None:
        """Register a custom steady state probe."""
        self._probes[probe_type] = probe
        logger.info(f"Registered probe type: {probe_type}")
    
    async def run(
        self,
        experiment: Experiment,
        dry_run: bool = False,
    ) -> ExperimentResult:
        """
        Run a chaos experiment.
        
        Args:
            experiment: Experiment to run
            dry_run: Dry run mode
            
        Returns:
            Experiment result
        """
        dry_run = dry_run or experiment.dry_run
        
        result = ExperimentResult(
            experiment_id=experiment.id,
            success=False,
            status=ExperimentStatus.PENDING,
            started_at=datetime.utcnow(),
        )
        
        # Track active experiment
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.utcnow()
        self._active[experiment.id] = experiment
        
        try:
            logger.info(f"Starting experiment: {experiment.name} (id={experiment.id})")
            result.add_event("start", f"Starting experiment: {experiment.name}")
            
            # Phase 1: Validate steady state before
            logger.info("Phase 1: Validating steady state (before)")
            steady_before = await self._validate_steady_state(
                experiment.steady_state, result
            )
            result.steady_state_met_before = steady_before
            
            if not steady_before:
                result.message = "Steady state not met before experiment"
                result.status = ExperimentStatus.FAILED
                result.add_event("abort", "Steady state not met before experiment")
                
                if experiment.abort_on_failure:
                    return result
            
            # Phase 2: Warmup
            if experiment.warmup_seconds > 0:
                logger.info(f"Phase 2: Warmup ({experiment.warmup_seconds}s)")
                result.add_event("warmup", f"Warmup period: {experiment.warmup_seconds}s")
                await asyncio.sleep(experiment.warmup_seconds)
            
            # Phase 3: Inject faults
            logger.info(f"Phase 3: Injecting {len(experiment.faults)} faults")
            result.add_event("inject", f"Injecting {len(experiment.faults)} faults")
            
            injection_tasks = []
            for fault in experiment.faults:
                if dry_run:
                    logger.info(f"[DRY RUN] Would inject: {fault.type.value}")
                    result.add_event(
                        "dry_run",
                        f"Would inject {fault.type.value} on {fault.target.name}",
                    )
                else:
                    task = self._inject_fault(fault, experiment.duration_seconds)
                    injection_tasks.append(task)
            
            # Run fault injections
            if injection_tasks:
                injection_results = await asyncio.gather(
                    *injection_tasks,
                    return_exceptions=True,
                )
                
                for i, res in enumerate(injection_results):
                    if isinstance(res, Exception):
                        result.errors.append(str(res))
                        logger.error(f"Fault injection failed: {res}")
            
            # Phase 4: Monitor during fault
            logger.info("Phase 4: Monitoring steady state during fault")
            
            # Validate steady state periodically during fault
            monitor_interval = 10  # seconds
            monitor_checks = experiment.duration_seconds // monitor_interval
            
            all_checks_passed = True
            for i in range(monitor_checks):
                await asyncio.sleep(monitor_interval)
                
                steady_during = await self._validate_steady_state(
                    experiment.steady_state, result, silent=True
                )
                
                if not steady_during:
                    all_checks_passed = False
                    result.add_event(
                        "steady_state_violation",
                        f"Steady state violated at {(i+1) * monitor_interval}s",
                    )
                    
                    if experiment.rollback_on_steady_state_failure:
                        logger.warning("Steady state violated, initiating rollback")
                        await self._rollback_faults(experiment.faults)
                        result.was_rolled_back = True
                        result.rollback_success = True
                        break
            
            result.steady_state_met_during = all_checks_passed
            
            # Phase 5: Stop faults (if not already rolled back)
            if not result.was_rolled_back:
                logger.info("Phase 5: Stopping faults")
                result.add_event("stop_faults", "Stopping fault injection")
                await self._stop_faults(experiment.faults)
            
            # Phase 6: Cooldown
            if experiment.cooldown_seconds > 0:
                logger.info(f"Phase 6: Cooldown ({experiment.cooldown_seconds}s)")
                result.add_event("cooldown", f"Cooldown period: {experiment.cooldown_seconds}s")
                await asyncio.sleep(experiment.cooldown_seconds)
            
            # Phase 7: Validate steady state after
            logger.info("Phase 7: Validating steady state (after)")
            steady_after = await self._validate_steady_state(
                experiment.steady_state, result
            )
            result.steady_state_met_after = steady_after
            
            # Determine overall success
            result.success = (
                result.steady_state_met_before and
                result.steady_state_met_during and
                result.steady_state_met_after and
                not result.errors
            )
            
            result.status = (
                ExperimentStatus.COMPLETED if result.success
                else ExperimentStatus.FAILED
            )
            
            result.message = (
                "Experiment completed successfully"
                if result.success
                else "Experiment failed: " + (
                    result.errors[0] if result.errors
                    else "Steady state not maintained"
                )
            )
            
            result.add_event(
                "complete",
                result.message,
                {"success": result.success},
            )
            
        except Exception as e:
            result.status = ExperimentStatus.FAILED
            result.message = str(e)
            result.errors.append(str(e))
            result.add_event("error", str(e))
            
            logger.error(f"Experiment failed: {e}", exc_info=True)
            
            # Attempt rollback
            if experiment.auto_rollback:
                try:
                    await self._rollback_faults(experiment.faults)
                    result.was_rolled_back = True
                    result.rollback_success = True
                except Exception as re:
                    result.rollback_success = False
                    result.errors.append(f"Rollback failed: {re}")
        
        finally:
            result.completed_at = datetime.utcnow()
            experiment.status = result.status
            experiment.completed_at = datetime.utcnow()
            experiment.result = result
            
            # Move to history
            self._active.pop(experiment.id, None)
            self._history.append(experiment)
        
        logger.info(
            f"Experiment {experiment.name} completed: "
            f"{'SUCCESS' if result.success else 'FAILED'}"
        )
        
        return result
    
    async def pause(self, experiment_id: UUID) -> bool:
        """Pause an active experiment."""
        experiment = self._active.get(experiment_id)
        if not experiment:
            return False
        
        experiment.status = ExperimentStatus.PAUSED
        
        # Stop all faults
        await self._stop_faults(experiment.faults)
        
        logger.info(f"Paused experiment: {experiment.name}")
        return True
    
    async def resume(self, experiment_id: UUID) -> bool:
        """Resume a paused experiment."""
        experiment = self._active.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.PAUSED:
            return False
        
        experiment.status = ExperimentStatus.RUNNING
        
        # Re-inject faults
        # This is simplified - real implementation would track remaining time
        logger.info(f"Resumed experiment: {experiment.name}")
        return True
    
    async def cancel(self, experiment_id: UUID) -> bool:
        """Cancel an active experiment."""
        experiment = self._active.get(experiment_id)
        if not experiment:
            return False
        
        experiment.status = ExperimentStatus.CANCELLED
        
        # Stop all faults and rollback
        await self._stop_faults(experiment.faults)
        await self._rollback_faults(experiment.faults)
        
        self._active.pop(experiment_id, None)
        self._history.append(experiment)
        
        logger.info(f"Cancelled experiment: {experiment.name}")
        return True
    
    async def _validate_steady_state(
        self,
        hypotheses: list[SteadyStateHypothesis],
        result: ExperimentResult,
        silent: bool = False,
    ) -> bool:
        """Validate all steady state hypotheses."""
        if not hypotheses:
            return True
        
        all_passed = True
        
        for hypothesis in hypotheses:
            probe = self._probes.get(hypothesis.probe_type)
            
            if not probe:
                logger.warning(f"Unknown probe type: {hypothesis.probe_type}")
                continue
            
            try:
                passed = await probe(hypothesis)
                
                if not passed:
                    all_passed = False
                    if not silent:
                        result.add_event(
                            "steady_state_check",
                            f"Hypothesis '{hypothesis.name}' failed",
                            {"hypothesis": hypothesis.name, "passed": False},
                        )
                else:
                    if not silent:
                        result.add_event(
                            "steady_state_check",
                            f"Hypothesis '{hypothesis.name}' passed",
                            {"hypothesis": hypothesis.name, "passed": True},
                        )
                        
            except Exception as e:
                all_passed = False
                logger.error(f"Steady state check failed: {e}")
                if not silent:
                    result.add_event(
                        "steady_state_error",
                        f"Hypothesis '{hypothesis.name}' error: {e}",
                    )
        
        return all_passed
    
    async def _inject_fault(
        self,
        fault: Fault,
        duration: int,
    ) -> None:
        """Inject a single fault."""
        if self._fault_injector:
            await self._fault_injector.inject(fault, duration)
        else:
            # Simulate fault injection
            logger.info(f"Injecting fault: {fault.type.value} for {duration}s")
            await asyncio.sleep(duration)
    
    async def _stop_faults(self, faults: list[Fault]) -> None:
        """Stop all injected faults."""
        for fault in faults:
            if self._fault_injector:
                await self._fault_injector.stop(fault.id)
            else:
                logger.info(f"Stopping fault: {fault.type.value}")
    
    async def _rollback_faults(self, faults: list[Fault]) -> None:
        """Rollback all faults."""
        for fault in faults:
            if self._fault_injector:
                await self._fault_injector.rollback(fault.id)
            else:
                logger.info(f"Rolling back fault: {fault.type.value}")
    
    async def _http_probe(self, hypothesis: SteadyStateHypothesis) -> bool:
        """HTTP health check probe."""
        import httpx
        
        if not hypothesis.endpoint:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    hypothesis.endpoint,
                    timeout=hypothesis.timeout_seconds,
                )
                
                if hypothesis.expected_status:
                    return response.status_code == hypothesis.expected_status
                
                return response.status_code < 400
                
        except Exception as e:
            logger.debug(f"HTTP probe failed: {e}")
            return False
    
    async def _tcp_probe(self, hypothesis: SteadyStateHypothesis) -> bool:
        """TCP connection probe."""
        import socket
        
        if not hypothesis.endpoint:
            return False
        
        try:
            # Parse host:port
            parts = hypothesis.endpoint.replace("tcp://", "").split(":")
            host = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 80
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(hypothesis.timeout_seconds)
            result = sock.connect_ex((host, port))
            sock.close()
            
            return result == 0
            
        except Exception as e:
            logger.debug(f"TCP probe failed: {e}")
            return False
    
    async def _prometheus_probe(self, hypothesis: SteadyStateHypothesis) -> bool:
        """Prometheus query probe."""
        import httpx
        
        if not hypothesis.query:
            return False
        
        prometheus_url = hypothesis.endpoint or "http://prometheus:9090"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{prometheus_url}/api/v1/query",
                    params={"query": hypothesis.query},
                    timeout=hypothesis.timeout_seconds,
                )
                
                data = response.json()
                
                if data.get("status") != "success":
                    return False
                
                results = data.get("data", {}).get("result", [])
                
                if not results:
                    return hypothesis.expected_value is None
                
                # Get first result value
                value = float(results[0].get("value", [0, 0])[1])
                
                if hypothesis.threshold is not None:
                    return value <= hypothesis.threshold
                
                if hypothesis.expected_value is not None:
                    tolerance = hypothesis.tolerance * abs(hypothesis.expected_value)
                    return abs(value - hypothesis.expected_value) <= tolerance
                
                return True
                
        except Exception as e:
            logger.debug(f"Prometheus probe failed: {e}")
            return False
    
    async def _command_probe(self, hypothesis: SteadyStateHypothesis) -> bool:
        """Command execution probe."""
        if not hypothesis.command:
            return False
        
        try:
            process = await asyncio.create_subprocess_shell(
                hypothesis.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=hypothesis.timeout_seconds,
            )
            
            return process.returncode == 0
            
        except Exception as e:
            logger.debug(f"Command probe failed: {e}")
            return False
    
    def get_active_experiments(self) -> list[Experiment]:
        """Get all active experiments."""
        return list(self._active.values())
    
    def get_experiment_history(
        self,
        limit: int = 100,
    ) -> list[Experiment]:
        """Get experiment history."""
        return self._history[-limit:]
