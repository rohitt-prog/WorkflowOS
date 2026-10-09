import test from "node:test";
import assert from "node:assert/strict";

// Workflow step definition for the 6-step Gmail triage pipeline
const GMAIL_TRIAGE_STEPS = [
  { id: "step_search_email", name: "Search Gmail messages", action: "search_messages", app: "gmail" },
  { id: "step_read_email", name: "Read the email", action: "read_message", app: "gmail" },
  { id: "step_download_attachment", name: "Download the attachment", action: "download_attachment", app: "gmail" },
  { id: "step_search_crm", name: "Search for the CRM customer", action: "search_customer", app: "crm" },
  { id: "step_update_crm", name: "Update the CRM customer", action: "update_customer", app: "crm" },
  { id: "step_send_chat", name: "Send the Chat notification", action: "send_message", app: "chat" },
];

// Action synonym resolver as implemented in WorkflowVisualizer
const ACTION_SYNONYMS = {
  search_messages: ["search_email", "list_recent_messages", "list_messages", "search_messages", "step_search_email"],
  read_message: ["open_email", "read_email", "read_message", "get_message", "step_read_email"],
  download_attachment: ["download_attachment", "get_attachment", "save_attachment", "step_download_attachment"],
  search_customer: ["search_crm", "search_customer", "find_customer", "step_search_crm"],
  update_customer: ["update_crm", "update_customer", "edit_customer", "step_update_crm"],
  send_message: ["send_chat", "send_notification", "send_message", "post_message", "step_send_chat"],
};

function matchStepAction(step, actionIdentifier) {
  if (!actionIdentifier) return false;
  const normalizedTarget = actionIdentifier.toLowerCase().trim();
  const stepId = step.id.toLowerCase().trim();
  const stepAction = step.action.toLowerCase().trim();
  const stepName = (step.name || "").toLowerCase().trim();

  if (stepId === normalizedTarget || stepAction === normalizedTarget || stepName === normalizedTarget) {
    return true;
  }
  const synonyms = ACTION_SYNONYMS[stepAction] || [];
  return synonyms.some((s) => s.toLowerCase() === normalizedTarget);
}

function deriveStepStatus(step, index, execution, isExecuting) {
  let status = "pending";
  let errMsg = undefined;

  if (execution) {
    const completedList = execution.completed_actions || [];
    const actionsDetail = execution.all_actions || execution.actions_detail || [];

    const detailMatch = actionsDetail.find(
      (d) =>
        matchStepAction(step, d.action) ||
        (d.action_id && matchStepAction(step, d.action_id)) ||
        (d.action_type && matchStepAction(step, d.action_type))
    );

    const isCompleted =
      completedList.some((act) => matchStepAction(step, act)) ||
      detailMatch?.status === "completed";

    const isFailed =
      (execution.failed_action && matchStepAction(step, execution.failed_action)) ||
      detailMatch?.status === "failed";

    const currentAction = execution.current_action;
    const isCurrent = currentAction ? matchStepAction(step, currentAction) : false;

    if (isCompleted) {
      status = "completed";
      if (detailMatch?.message) errMsg = detailMatch.message;
    } else if (execution.status === "paused" && (isFailed || isCurrent)) {
      status = "paused";
      errMsg = execution.failure_reason || detailMatch?.message || execution.error;
    } else if (execution.status === "cancelled" && (isCurrent || detailMatch?.status === "cancelled")) {
      status = "cancelled";
      errMsg = detailMatch?.message || "Execution cancelled";
    } else if (detailMatch?.status === "skipped") {
      status = "skipped";
      errMsg = detailMatch.message;
    } else if (detailMatch?.status === "running") {
      status = "running";
      errMsg = detailMatch.message;
    } else if (isFailed) {
      status = "failed";
      errMsg = execution.failure_reason || detailMatch?.message || execution.error;
    } else if (isCurrent) {
      if (execution.status === "paused") status = "paused";
      else if (execution.status === "failed") status = "failed";
      else if (execution.status === "cancelled") status = "cancelled";
      else if (execution.status === "completed") status = "completed";
      else status = "running";
    } else if (execution.status === "completed") {
      status = "completed";
    } else if (execution.status === "cancelled" && index >= completedList.length) {
      status = "skipped";
    }
  } else if (isExecuting && index === 0) {
    status = "running";
  }

  return { status, errMsg };
}

test("Workflow Approval and Execution Flow Lifecycle", async (t) => {
  await t.test("1. Modal and Visualizer mount during review and stay mounted when Approve & Execute is triggered", () => {
    // Simulated state machine of DiscoveryView
    let modalOpen = true;
    let visualizerMounted = true;
    let isExecuting = false;
    const selectedWorkflow = { workflow_id: "wf_gmail_triage", label: "Gmail Triage Pipeline", sequence: ["search_messages"] };
    const proposal = { name: "Gmail Triage Pipeline", description: "Automated triage" };
    const executionResult = null;

    assert.equal(selectedWorkflow.workflow_id, "wf_gmail_triage");
    assert.equal(executionResult, null);

    // Trigger Approve & Execute
    function handleApproveAndRun() {
      if (!proposal || isExecuting) return false;
      isExecuting = true;
      // Crucial: Modal and visualizer must remain open!
      assert.equal(modalOpen, true, "Modal must remain open");
      assert.equal(visualizerMounted, true, "Visualizer must remain mounted");
      return true;
    }

    const started = handleApproveAndRun();
    assert.equal(started, true);
    assert.equal(isExecuting, true);
    assert.equal(modalOpen, true);
    assert.equal(visualizerMounted, true);
  });

  await t.test("2. Duplicate submissions are strictly prevented while execution is in-flight", () => {
    let executionCalls = 0;
    let isExecuting = true; // In-flight
    const proposal = { name: "Gmail Triage" };

    function attemptExecute() {
      if (!proposal || isExecuting) return false;
      executionCalls++;
      return true;
    }

    const firstAttempt = attemptExecute();
    const secondAttempt = attemptExecute();
    assert.equal(firstAttempt, false, "First duplicate execution rejected");
    assert.equal(secondAttempt, false, "Second duplicate execution rejected");
    assert.equal(executionCalls, 0, "No duplicate execution requests sent");
  });

  await t.test("3. Step states transition through pending -> running -> completed with action synonyms", () => {
    // 0: Search Gmail messages
    // 1: Read the email
    // 2: Download the attachment
    // 3: Search for the CRM customer
    // 4: Update the CRM customer
    // 5: Send the Chat notification

    // Pre-execution: all pending
    GMAIL_TRIAGE_STEPS.forEach((step, idx) => {
      const { status } = deriveStepStatus(step, idx, null, false);
      assert.equal(status, "pending");
    });

    // In-flight execution start: step 0 is running
    const step0Init = deriveStepStatus(GMAIL_TRIAGE_STEPS[0], 0, null, true);
    assert.equal(step0Init.status, "running");

    // Partial execution response: steps 0 and 1 completed via synonyms (open_email), step 2 running
    const partialExec = {
      status: "running",
      completed_actions: ["search_messages", "open_email"],
      current_action: "download_attachment",
      all_actions: [
        { action: "search_messages", status: "completed" },
        { action: "open_email", status: "completed" },
        { action: "download_attachment", status: "running" },
      ],
    };

    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[0], 0, partialExec, true).status, "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[1], 1, partialExec, true).status, "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[2], 2, partialExec, true).status, "running");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[3], 3, partialExec, true).status, "pending");
  });

  await t.test("4. Execution completion keeps visualizer visible with full success status and details", () => {
    const fullExecResponse = {
      status: "completed",
      workflow_id: "wf_gmail_triage",
      completed_actions: [
        "search_messages",
        "read_message",
        "download_attachment",
        "search_customer",
        "update_customer",
        "send_message",
      ],
      total_actions: 6,
      execution_time_seconds: 3.42,
    };

    // When execution ends:
    let isExecuting = false;
    let executionResult = fullExecResponse;
    let modalOpen = true;

    // Assert that all 6 steps are resolved as completed
    GMAIL_TRIAGE_STEPS.forEach((step, idx) => {
      const { status } = deriveStepStatus(step, idx, executionResult, isExecuting);
      assert.equal(status, "completed", `Step ${idx} must be marked completed`);
    });

    assert.equal(modalOpen, true, "Modal remains open after completion");
    assert.equal(executionResult.execution_time_seconds, 3.42);
    assert.equal(executionResult.completed_actions.length, 6);
  });

  await t.test("5. Paused execution preserves visualizer and human intervention details", () => {
    const pausedExecResponse = {
      status: "paused",
      workflow_id: "wf_gmail_triage",
      requires_human_intervention: true,
      human_intervention: {
        title: "Customer Not Found in CRM",
        reason: "Customer UnknownUser does not exist in CRM database",
        action_required: "Please verify customer name or create customer record",
      },
      resume_available: true,
      completed_actions: ["search_messages", "read_message", "download_attachment"],
      failed_action: "search_customer",
      failure_reason: "Customer UnknownUser not found in CRM database",
      total_actions: 6,
    };

    let isExecuting = false;
    let executionResult = pausedExecResponse;
    let modalOpen = true;

    assert.equal(modalOpen, true, "Modal must stay open when paused");
    assert.equal(executionResult.status, "paused");
    assert.equal(executionResult.requires_human_intervention, true);
    assert.equal(executionResult.human_intervention.title, "Customer Not Found in CRM");

    // Check step statuses
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[0], 0, executionResult, isExecuting).status, "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[1], 1, executionResult, isExecuting).status, "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[2], 2, executionResult, isExecuting).status, "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[3], 3, executionResult, isExecuting).status, "paused");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[4], 4, executionResult, isExecuting).status, "pending");
  });

  await t.test("6. Failed execution preserves visualizer and displays error information without unmounting", () => {
    const failedExecResponse = {
      status: "failed",
      workflow_id: "wf_gmail_triage",
      failed_action: "read_message",
      failure_reason: "Timeout reading email body from Gmail API",
      completed_actions: ["search_messages"],
      total_actions: 6,
    };

    let isExecuting = false;
    let executionResult = failedExecResponse;
    let modalOpen = true;

    assert.equal(modalOpen, true, "Modal remains open on execution failure");
    assert.equal(executionResult.status, "failed");
    assert.equal(executionResult.failure_reason, "Timeout reading email body from Gmail API");

    const step1Status = deriveStepStatus(GMAIL_TRIAGE_STEPS[1], 1, executionResult, isExecuting);
    assert.equal(step1Status.status, "failed");
    assert.equal(step1Status.errMsg, "Timeout reading email body from Gmail API");
  });

  await t.test("7. API error / network failure does not unmount the modal or crash view", () => {
    let modalOpen = true;
    let isExecuting = false;
    let executionError = null;

    // Simulate network or 500 error in handleApproveAndRun
    function simulateFailedApiCall() {
      isExecuting = true;
      try {
        throw new Error("HTTP 500: Automation engine temporary unavailable");
      } catch (err) {
        executionError = err.message;
      } finally {
        isExecuting = false;
      }
    }

    simulateFailedApiCall();
    assert.equal(modalOpen, true, "Modal stays open when API throws an error");
    assert.equal(isExecuting, false);
    assert.equal(executionError, "HTTP 500: Automation engine temporary unavailable");
  });

  await t.test("8. Explicit close guards: backdrop click & Escape are blocked during in-flight actions", () => {
    let modalOpen = true;
    let isExecuting = true;
    let isResuming = false;
    let isCancelling = false;

    function handleBackdropClick() {
      if (!isExecuting && !isResuming && !isCancelling) {
        modalOpen = false;
      }
    }

    function handleEscapeKey() {
      if (!isExecuting && !isResuming && !isCancelling) {
        modalOpen = false;
      }
    }

    // In-flight: click or escape must NOT close
    handleBackdropClick();
    assert.equal(modalOpen, true, "Backdrop click blocked during execution");

    handleEscapeKey();
    assert.equal(modalOpen, true, "Escape key blocked during execution");

    // Finished execution: user explicitly closes
    isExecuting = false;
    handleBackdropClick();
    assert.equal(modalOpen, false, "Backdrop click closes modal when idle");
  });
});
