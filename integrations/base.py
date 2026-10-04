"""
WorkFlowOS Phase 7.1: Base Integration Adapter Abstraction

Defines the reusable, extensible integration contract (BaseIntegrationAdapter)
enforcing connection lifecycles, action capability declarations, strict input
validation, and structured result emission with credential safety.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Callable

from integrations.models import (
    IntegrationMetadata,
    IntegrationStatus,
    IntegrationActionDefinition,
    IntegrationActionResult,
    IntegrationSummary,
    ParameterType,
    UnknownIntegrationError,
    UnsupportedActionError,
    IntegrationConnectionError,
    IntegrationValidationError,
)
from integrations.credentials import sanitize_credential_dict, sanitize_log_message

logger = logging.getLogger(__name__)


class BaseIntegrationAdapter(ABC):
    """
    Abstract base class for all WorkFlowOS integration adapters.

    Provides:
    - Identification and metadata declarations.
    - Connection state machine (connect/disconnect/error).
    - Capability and permission declarations.
    - Schema-based input validation.
    - Structured execution and error containment.
    """

    def __init__(self, metadata: IntegrationMetadata):
        self.metadata = metadata
        self._status: IntegrationStatus = IntegrationStatus.DISCONNECTED
        self._connected_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._actions: Dict[str, IntegrationActionDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._register_capabilities()

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def status(self) -> IntegrationStatus:
        return self._status

    @property
    def is_connected(self) -> bool:
        return self._status == IntegrationStatus.CONNECTED

    @property
    def connected_at(self) -> Optional[str]:
        return self._connected_at

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def declared_actions(self) -> List[IntegrationActionDefinition]:
        return list(self._actions.values())

    @property
    def declared_action_names(self) -> List[str]:
        return list(self._actions.keys())

    def get_action(self, action_name: str) -> Optional[IntegrationActionDefinition]:
        """Retrieves declared ActionDefinition for action_name, or None."""
        return self._actions.get(action_name)

    @abstractmethod
    def _register_capabilities(self) -> None:
        """Subclasses declare their actions, parameter schemas, and handlers here."""
        pass

    def register_action(
        self,
        action_def: IntegrationActionDefinition,
        handler: Callable
    ) -> None:
        """
        Registers an action capability and its execution handler.
        """
        self._actions[action_def.name] = action_def
        self._handlers[action_def.name] = handler
        logger.debug(f"[{self.id}] Registered action capability: '{action_def.name}'")

    async def connect(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """
        Establishes connection to the service.
        Subclasses should override _do_connect for provider-specific authentication.
        """
        try:
            logger.info(f"[{self.id}] Initiating connection...")
            success = await self._do_connect(credentials=credentials)
            if success:
                self._status = IntegrationStatus.CONNECTED
                self._connected_at = datetime.now(timezone.utc).isoformat()
                self._last_error = None
                logger.info(f"[{self.id}] Successfully connected.")
                return True
            else:
                self._status = IntegrationStatus.ERROR
                self._last_error = self._last_error or "Connection rejected by adapter"
                logger.warning(f"[{self.id}] Connection failed: {self._last_error}")
                return False
        except Exception as e:
            self._status = IntegrationStatus.ERROR
            safe_err = sanitize_log_message(str(e))
            self._last_error = safe_err
            logger.error(f"[{self.id}] Error during connection: {safe_err}")
            return False

    async def disconnect(self) -> bool:
        """
        Disconnects the integration adapter and cleans up active resources.
        """
        try:
            logger.info(f"[{self.id}] Disconnecting...")
            await self._do_disconnect()
            self._status = IntegrationStatus.DISCONNECTED
            self._connected_at = None
            self._last_error = None
            logger.info(f"[{self.id}] Disconnected successfully.")
            return True
        except Exception as e:
            safe_err = sanitize_log_message(str(e))
            self._last_error = safe_err
            logger.error(f"[{self.id}] Error during disconnect: {safe_err}")
            return False

    async def _do_connect(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Default hook for connecting. Can be overridden by subclasses."""
        return True

    async def _do_disconnect(self) -> None:
        """Default hook for disconnecting. Can be overridden by subclasses."""
        pass

    def validate_action_inputs(
        self,
        action_name: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates the provided parameters against the declared ActionParameterDefinition schema.

        :param action_name: Target action name.
        :param parameters: Dict of parameters provided for execution.
        :return: (True, None) if valid; (False, error_message) if invalid.
        """
        if action_name not in self._actions:
            return False, f"Action '{action_name}' is not supported by integration '{self.id}'."

        action_def = self._actions[action_name]
        params = parameters or {}

        for param_def in action_def.parameters:
            val = params.get(param_def.name)

            # Check required fields
            if param_def.required and (val is None or val == ""):
                return False, f"Missing required parameter '{param_def.name}' for action '{action_name}'."

            # If parameter was omitted but optional, skip type check
            if val is None:
                continue

            # Check type validity
            if param_def.type == ParameterType.STRING:
                if not isinstance(val, str):
                    return False, f"Parameter '{param_def.name}' must be a string, got {type(val).__name__}."
            elif param_def.type == ParameterType.INTEGER:
                if not isinstance(val, int) or isinstance(val, bool):
                    return False, f"Parameter '{param_def.name}' must be an integer, got {type(val).__name__}."
            elif param_def.type == ParameterType.NUMBER:
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    return False, f"Parameter '{param_def.name}' must be a number, got {type(val).__name__}."
            elif param_def.type == ParameterType.BOOLEAN:
                if not isinstance(val, bool):
                    return False, f"Parameter '{param_def.name}' must be a boolean, got {type(val).__name__}."
            elif param_def.type == ParameterType.OBJECT:
                if not isinstance(val, dict):
                    return False, f"Parameter '{param_def.name}' must be an object/dict, got {type(val).__name__}."
            elif param_def.type == ParameterType.ARRAY:
                if not isinstance(val, list):
                    return False, f"Parameter '{param_def.name}' must be a list/array, got {type(val).__name__}."

            # Check allowed values
            if param_def.allowed_values is not None:
                if val not in param_def.allowed_values:
                    return (
                        False,
                        f"Parameter '{param_def.name}' value '{val}' is not in allowed values: {param_def.allowed_values}."
                    )

        return True, None

    async def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> IntegrationActionResult:
        """
        Executes a registered action on this adapter.
        Performs connection check, input validation, execution, and error sanitization.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Connection check
        if not self.is_connected:
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=f"Integration '{self.id}' is disconnected. Please connect before executing actions.",
                error_code="INTEGRATION_DISCONNECTED",
                timestamp=now_iso,
            )

        # 2. Capability check
        if action_name not in self._actions:
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=f"Action '{action_name}' is not supported by integration '{self.id}'. Supported: {self.declared_action_names}",
                error_code="UNSUPPORTED_ACTION",
                timestamp=now_iso,
            )

        # 3. Input validation
        is_valid, validation_err = self.validate_action_inputs(action_name, parameters)
        if not is_valid:
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=validation_err or "Invalid action parameters",
                error_code="VALIDATION_ERROR",
                timestamp=now_iso,
            )

        # 4. Action dispatch
        handler = self._handlers.get(action_name)
        if not handler:
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=f"No execution handler registered for action '{action_name}'.",
                error_code="HANDLER_NOT_FOUND",
                timestamp=now_iso,
            )

        try:
            # Build merged parameters applying defaults
            merged_params = dict(parameters or {})
            for p_def in self._actions[action_name].parameters:
                if p_def.name not in merged_params and p_def.default is not None:
                    merged_params[p_def.name] = p_def.default

            res = await handler(parameters=merged_params, context=context or {})

            # Standardize to IntegrationActionResult
            if isinstance(res, IntegrationActionResult):
                clean_data = sanitize_credential_dict(res.data) if res.data else None
                return res.model_copy(update={"data": clean_data})
            elif isinstance(res, dict):
                clean_dict = sanitize_credential_dict(res)
                return IntegrationActionResult(
                    action_name=action_name,
                    success=True,
                    message="Action executed successfully",
                    data=clean_dict,
                    timestamp=now_iso,
                )
            else:
                return IntegrationActionResult(
                    action_name=action_name,
                    success=True,
                    message="Action executed successfully",
                    data={"result": str(res)},
                    timestamp=now_iso,
                )

        except IntegrationValidationError as e:
            safe_msg = sanitize_log_message(str(e))
            logger.error(f"[{self.id}] Action '{action_name}' validation error: {safe_msg}")
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=safe_msg,
                error_code="VALIDATION_ERROR",
                timestamp=now_iso,
            )
        except IntegrationConnectionError as e:
            safe_msg = sanitize_log_message(str(e))
            logger.error(f"[{self.id}] Action '{action_name}' connection error: {safe_msg}")
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=safe_msg,
                error_code="CONNECTION_ERROR",
                timestamp=now_iso,
            )
        except Exception as e:
            safe_msg = sanitize_log_message(str(e))
            logger.error(f"[{self.id}] Action '{action_name}' execution error: {safe_msg}")
            return IntegrationActionResult(
                action_name=action_name,
                success=False,
                message=f"Action execution failed: {safe_msg}",
                error_code="EXECUTION_ERROR",
                timestamp=now_iso,
            )

    def to_summary(self) -> IntegrationSummary:
        """Builds an API and UI summary of this integration adapter."""
        return IntegrationSummary(
            id=self.metadata.id,
            name=self.metadata.name,
            description=self.metadata.description,
            version=self.metadata.version,
            category=self.metadata.category,
            icon=self.metadata.icon,
            is_mock=self.metadata.is_mock,
            disclaimer=self.metadata.disclaimer,
            status=self._status,
            is_connected=self.is_connected,
            connected_at=self._connected_at,
            last_error=self._last_error,
            actions=self.declared_actions,
        )
