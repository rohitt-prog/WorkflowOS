from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class WorkflowTrigger(BaseModel):
    """
    Describes the trigger event that initiates the workflow.
    """
    type: str = Field(
        ...,
        description="Event verb or trigger type (e.g. 'new_email', 'webhook')"
    )
    application: str = Field(
        ...,
        description="Application where the trigger originated (e.g. 'demo_email', 'demo_crm')"
    )
    description: str = Field(
        ...,
        description="Human-readable explanation of the triggering condition"
    )


class WorkflowAction(BaseModel):
    """
    Describes an individual step in the workflow action sequence.
    """
    type: str = Field(
        ...,
        description="Action type or verb (e.g. 'open_email', 'download_attachment')"
    )
    application: str = Field(
        ...,
        description="Application in which the action is performed (e.g. 'demo_email', 'demo_crm')"
    )
    description: str = Field(
        ...,
        description="Human-readable explanation of what this action accomplishes"
    )
    target: str = Field(
        ...,
        description="The subject or entity targeted by the action (e.g. 'customer_request', 'attachment')"
    )


class WorkflowProposal(BaseModel):
    """
    Structured AI-inferred workflow understanding proposal for human review.
    """
    name: str = Field(
        ...,
        description="Descriptive, human-readable name of the workflow"
    )
    intent: str = Field(
        ...,
        description="Inferred business or operational intent of the workflow"
    )
    trigger: WorkflowTrigger = Field(
        ...,
        description="The initial trigger event initiating the workflow"
    )
    actions: List[WorkflowAction] = Field(
        ...,
        description="Ordered sequence of actions comprising the workflow"
    )
    variables: List[str] = Field(
        default_factory=list,
        description="List of identified dynamic variables (e.g. customer_name, attachment)"
    )
    applications: List[str] = Field(
        ...,
        description="List of distinct applications involved in the workflow"
    )
    requires_approval: bool = Field(
        default=True,
        description="Whether human approval is required before execution (always True for safety)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Process Customer Request",
                "intent": "Process incoming customer requests and update the CRM",
                "trigger": {
                    "type": "new_email",
                    "application": "demo_email",
                    "description": "A customer request email is received"
                },
                "actions": [
                    {
                        "type": "open_email",
                        "application": "demo_email",
                        "description": "Open the customer request email",
                        "target": "customer_request"
                    },
                    {
                        "type": "download_attachment",
                        "application": "demo_email",
                        "description": "Download the email attachment",
                        "target": "attachment"
                    },
                    {
                        "type": "search_customer",
                        "application": "demo_crm",
                        "description": "Search for the customer in the CRM",
                        "target": "customer"
                    },
                    {
                        "type": "update_customer",
                        "application": "demo_crm",
                        "description": "Update the customer's CRM record",
                        "target": "customer"
                    },
                    {
                        "type": "send_message",
                        "application": "demo_messaging",
                        "description": "Notify the support team",
                        "target": "#client-support"
                    }
                ],
                "variables": [
                    "customer_name",
                    "attachment"
                ],
                "applications": [
                    "demo_email",
                    "demo_crm",
                    "demo_messaging"
                ],
                "requires_approval": True
            }
        }
    }


class GenerateWorkflowRequest(BaseModel):
    """
    Request payload for POST /api/ai/workflow/generate.
    Accepts raw sequence/applications or a full DiscoveredWorkflow object.
    """
    sequence: Optional[List[str]] = Field(
        None,
        description="Ordered list of event verbs defining the workflow"
    )
    applications: Optional[List[str]] = Field(
        default_factory=list,
        description="List of applications involved in the workflow"
    )
    workflow: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional full DiscoveredWorkflow object from Phase 2 discovery"
    )
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional context or session metadata"
    )


class GenerateWorkflowResponse(BaseModel):
    """
    Response payload for POST /api/ai/workflow/generate.
    """
    success: bool = Field(
        ...,
        description="Indicates whether the workflow proposal was successfully generated"
    )
    workflow: Optional[WorkflowProposal] = Field(
        None,
        description="The AI-generated workflow proposal"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if generation failed"
    )
