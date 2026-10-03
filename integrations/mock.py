"""
WorkFlowOS Phase 7.1: Clearly Labeled Mock Integration Adapter

A safe, isolated test fixture for validating integration lifecycles,
capability declarations, action dispatch, and error handling without
making external network requests or claiming to connect to real services.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from integrations.base import BaseIntegrationAdapter
from integrations.models import (
    IntegrationMetadata,
    IntegrationActionDefinition,
    ActionParameterDefinition,
    ParameterType,
    IntegrationActionResult,
)


class MockTestIntegrationAdapter(BaseIntegrationAdapter):
    """
    Mock integration adapter for testing and verification.
    Clearly marked as simulated; never communicates with external services.
    """

    def __init__(self, adapter_id: str = "mock_service"):
        metadata = IntegrationMetadata(
            id=adapter_id,
            name="Mock Test Integration",
            description=(
                "Safe, simulated integration adapter for testing connection states, "
                "credential redaction, and action routing without external network calls."
            ),
            version="1.0.0",
            category="testing",
            icon="flask",
            is_mock=True,
            disclaimer=(
                "NOTICE: This is an isolated mock test fixture. "
                "It does not communicate with any external SaaS or cloud service."
            ),
        )
        super().__init__(metadata=metadata)

    def _register_capabilities(self) -> None:
        """Declares safe mock actions with strict parameter schemas."""

        # 1. Safe mock action: mock_echo
        self.register_action(
            IntegrationActionDefinition(
                name="mock_echo",
                display_name="Echo Test Message",
                description="Echoes an input message back with an optional prefix for data flow validation.",
                parameters=[
                    ActionParameterDefinition(
                        name="message",
                        type=ParameterType.STRING,
                        required=True,
                        description="Input text string to echo back",
                    ),
                    ActionParameterDefinition(
                        name="prefix",
                        type=ParameterType.STRING,
                        required=False,
                        default="[MockEcho] ",
                        description="Optional prefix prepended to the returned message",
                    ),
                ],
                required_scopes=["test:read"],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
            ),
            handler=self._handle_mock_echo,
        )

        # 2. Safe mock action: simulate_ping
        self.register_action(
            IntegrationActionDefinition(
                name="simulate_ping",
                display_name="Ping Health Check",
                description="Simulates a lightweight API heartbeat/ping request.",
                parameters=[
                    ActionParameterDefinition(
                        name="payload",
                        type=ParameterType.STRING,
                        required=False,
                        default="ping",
                        description="Heartbeat identifier payload",
                    )
                ],
                required_scopes=["test:read"],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
            ),
            handler=self._handle_simulate_ping,
        )

        # 3. Action to test failure containment: simulate_failure
        self.register_action(
            IntegrationActionDefinition(
                name="simulate_failure",
                display_name="Simulate Action Failure",
                description="Simulates a controlled action failure to test error paths and recovery.",
                parameters=[
                    ActionParameterDefinition(
                        name="error_message",
                        type=ParameterType.STRING,
                        required=False,
                        default="Simulated failure for testing error handling",
                        description="Simulated failure message",
                    ),
                    ActionParameterDefinition(
                        name="error_code",
                        type=ParameterType.STRING,
                        required=False,
                        default="SIMULATED_FAILURE",
                        description="Simulated machine-readable error code",
                    ),
                ],
                required_scopes=["test:write"],
                is_safe=True,
                is_mutating=False,
                is_destructive=False,
                allow_direct_execution=True,
            ),
            handler=self._handle_simulate_failure,
        )

        # 4. Mutating mock action: simulate_mutating_write
        # Strictly forbidden from direct execution without workflow approval
        self.register_action(
            IntegrationActionDefinition(
                name="simulate_mutating_write",
                display_name="Simulate Mutating State Write",
                description=(
                    "Simulates an action that mutates external state. "
                    "Cannot be directly executed outside an approved workflow."
                ),
                parameters=[
                    ActionParameterDefinition(
                        name="target_id",
                        type=ParameterType.STRING,
                        required=True,
                        description="Entity ID to update",
                    ),
                    ActionParameterDefinition(
                        name="value",
                        type=ParameterType.STRING,
                        required=True,
                        description="Updated value to write",
                    ),
                ],
                required_scopes=["test:write"],
                is_safe=False,
                is_mutating=True,
                is_destructive=False,
                allow_direct_execution=False,
            ),
            handler=self._handle_simulate_mutating_write,
        )

    async def _handle_mock_echo(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes safe echo action."""
        msg = parameters.get("message", "")
        prefix = parameters.get("prefix", "[MockEcho] ")
        return {
            "echoed_message": f"{prefix}{msg}",
            "original_length": len(msg),
            "service": self.id,
            "is_simulated": True,
        }

    async def _handle_simulate_ping(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes ping action."""
        payload = parameters.get("payload", "ping")
        return {
            "pong": True,
            "payload": payload,
            "latency_ms": 1,
            "status": "healthy",
            "service": self.id,
            "is_simulated": True,
        }

    async def _handle_simulate_failure(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> IntegrationActionResult:
        """Returns a structured failure response for testing."""
        error_msg = parameters.get("error_message", "Simulated failure for testing error handling")
        error_code = parameters.get("error_code", "SIMULATED_FAILURE")
        return IntegrationActionResult(
            action_name="simulate_failure",
            success=False,
            message=error_msg,
            error_code=error_code,
            data={"simulated_error": True, "service": self.id},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def _handle_simulate_mutating_write(
        self,
        parameters: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Executes simulated mutating state write (only within approved workflows)."""
        target_id = parameters.get("target_id", "")
        value = parameters.get("value", "")
        return {
            "updated": True,
            "target_id": target_id,
            "value": value,
            "service": self.id,
            "is_simulated": True,
            "mutation_applied": True,
        }
