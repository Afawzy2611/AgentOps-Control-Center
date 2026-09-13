"""Optional Airbyte Agent SDK adapter for read-only external evidence."""

from typing import Any, Callable

from .external_evidence import AuthorizationDecision, EvidencePolicy, EvidenceStatus, ExternalContextProvider, ExternalEvidence, authorize_operation

_READ_OPERATIONS = {"inspect_connector", "read_skill_docs", "execute"}
_READ_ACTIONS = {"list", "get", "search", "read", "retrieve", "list_records", "get_record", "search_records"}


class AirbyteEvidenceProvider(ExternalContextProvider):
    provider_name = "airbyte"

    def __init__(self, policy: EvidencePolicy, connector_factory: Callable[[str], Any] | None = None, sdk_available: bool | None = None):
        if sdk_available is False:
            raise RuntimeError("Airbyte Agent SDK is not installed; install the optional Airbyte agent SDK to use this provider.")
        if connector_factory is None:
            try:
                from airbyte_agent_sdk import connect
            except ImportError as exc:
                raise RuntimeError("Airbyte Agent SDK is not installed; install the optional Airbyte agent SDK to use this provider.") from exc
            connector_factory = connect
        self.policy = policy
        self.connector_factory = connector_factory

    def inspect_capability(self, connector: str) -> dict[str, Any]:
        if authorize_operation(self.policy, self.provider_name, connector, "inspect_connector") is AuthorizationDecision.DENIED:
            return {"connector": connector, "authorized": False, "operations": []}
        client = self.connector_factory(connector)
        return {"connector": connector, "authorized": True, "operations": sorted(_READ_OPERATIONS), "capability": client.inspect_connector()}

    def execute(self, connector: str, operation: str, arguments: dict[str, Any]) -> ExternalEvidence:
        if operation not in _READ_OPERATIONS:
            return ExternalEvidence(self.provider_name, connector, operation, EvidenceStatus.FAILED, error="Unsupported external operation")
        if authorize_operation(self.policy, self.provider_name, connector, operation) is AuthorizationDecision.DENIED:
            return ExternalEvidence(self.provider_name, connector, operation, EvidenceStatus.FAILED, error="Operation denied by external evidence policy")

        client = self.connector_factory(connector)
        if operation == "inspect_connector":
            payload = client.inspect_connector()
        elif operation == "read_skill_docs":
            payload = client.read_skill_docs(section=arguments.get("section"))
        else:
            entity = arguments.get("entity")
            action = arguments.get("action")
            if not entity or not action:
                return ExternalEvidence(self.provider_name, connector, operation, EvidenceStatus.FAILED, error="Connector entity and action are required")
            if action.lower() not in _READ_ACTIONS:
                return ExternalEvidence(self.provider_name, connector, operation, EvidenceStatus.FAILED, error="Connector action is not read-only")
            payload = client.execute(entity, action, params=arguments.get("params", {}))

        if hasattr(payload, "model_dump"):
            payload = payload.model_dump(mode="json")
        return ExternalEvidence.success(self.provider_name, connector, operation, payload, provenance={"provider": "airbyte", "connector": connector})
