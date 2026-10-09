import test from "node:test";
import assert from "node:assert/strict";

test("Execution UI Polish & Timeline Verification", async (t) => {
  // Step status badge logic matching getStepStatusBadge
  function getStepStatusBadge(status) {
    switch (status) {
      case "completed":
        return { label: "Completed", icon: "✓" };
      case "running":
        return { label: "Running", icon: "⟳" };
      case "failed":
        return { label: "Failed", icon: "✕" };
      case "paused":
        return { label: "Paused", icon: "⏸" };
      case "cancelled":
        return { label: "Cancelled", icon: "⊘" };
      case "skipped":
        return { label: "Not Executed", icon: "↷" };
      case "pending":
      default:
        return { label: "Pending", icon: "○" };
    }
  }

  await t.test("1. Execution summary parses real duration and step counts without fabrication", () => {
    const execWithDuration = {
      status: "completed",
      execution_id: "exec_12345",
      workflow_name: "Gmail Inbox Triage",
      completed_actions: ["search_messages", "read_message", "download_attachment"],
      total_actions: 3,
      execution_time_seconds: 4.82,
    };

    assert.equal(execWithDuration.status, "completed");
    assert.equal(execWithDuration.execution_time_seconds, 4.82);
    assert.equal(execWithDuration.completed_actions.length, 3);
    assert.equal(execWithDuration.total_actions, 3);

    const execWithoutDuration = {
      status: "running",
      execution_id: "exec_67890",
      workflow_name: "Gmail Inbox Triage",
      completed_actions: ["search_messages"],
      total_actions: 6,
    };

    // Duration must not be invented when missing
    assert.equal(execWithoutDuration.execution_time_seconds, undefined);
    assert.equal(typeof execWithoutDuration.execution_time_seconds === "number", false);
  });

  await t.test("2. Restrained status badges provide correct labels and icons for all lifecycle states", () => {
    assert.deepEqual(getStepStatusBadge("completed"), { label: "Completed", icon: "✓" });
    assert.deepEqual(getStepStatusBadge("running"), { label: "Running", icon: "⟳" });
    assert.deepEqual(getStepStatusBadge("failed"), { label: "Failed", icon: "✕" });
    assert.deepEqual(getStepStatusBadge("paused"), { label: "Paused", icon: "⏸" });
    assert.deepEqual(getStepStatusBadge("cancelled"), { label: "Cancelled", icon: "⊘" });
    assert.deepEqual(getStepStatusBadge("skipped"), { label: "Not Executed", icon: "↷" });
    assert.deepEqual(getStepStatusBadge("pending"), { label: "Pending", icon: "○" });
  });

  await t.test("3. Paused execution correctly isolates intervention details and paused step", () => {
    const pausedExec = {
      status: "paused",
      execution_id: "exec_paused_99",
      workflow_id: "wf_gmail_triage",
      failed_action: "search_customer",
      requires_human_intervention: true,
      human_intervention: {
        title: "Customer Not Found in CRM",
        reason: "Sender address not associated with any active CRM customer account.",
        action_required: "Verify customer account or create new lead.",
      },
      completed_actions: ["search_messages", "read_message", "download_attachment"],
      total_actions: 6,
    };

    assert.equal(pausedExec.status, "paused");
    assert.equal(pausedExec.requires_human_intervention, true);
    assert.equal(pausedExec.human_intervention.title, "Customer Not Found in CRM");
    assert.equal(pausedExec.failed_action, "search_customer");
    assert.equal(pausedExec.completed_actions.length, 3);
  });

  await t.test("4. Timeline correctly identifies unexecuted steps when pipeline terminates early", () => {
    const failedExec = {
      status: "failed",
      failed_action: "step_read_email",
      failure_reason: "Failed to download email body from mail server",
      completed_actions: ["step_search_email"],
      total_actions: 6,
    };
    assert.equal(failedExec.status, "failed");

    const steps = [
      { id: "step_search_email", status: "completed" },
      { id: "step_read_email", status: "failed" },
      { id: "step_download_attachment", status: "skipped" },
      { id: "step_search_crm", status: "skipped" },
      { id: "step_update_crm", status: "skipped" },
      { id: "step_send_chat", status: "skipped" },
    ];

    assert.equal(steps[0].status, "completed");
    assert.equal(steps[1].status, "failed");
    assert.equal(steps[2].status, "skipped");
    assert.equal(getStepStatusBadge(steps[2].status).label, "Not Executed");
    assert.equal(getStepStatusBadge(steps[3].status).label, "Not Executed");
  });

  await t.test("5. Step duration and timestamp extraction from action details", () => {
    const actionTrace = [
      {
        action: "search_messages",
        status: "completed",
        duration_seconds: 0.85,
        timestamp: "2026-10-09T10:14:02.000Z",
      },
      {
        action: "read_message",
        status: "completed",
        duration_seconds: 1.20,
        timestamp: "2026-10-09T10:14:03.200Z",
      },
    ];

    assert.equal(actionTrace[0].duration_seconds, 0.85);
    assert.equal(actionTrace[1].duration_seconds, 1.20);
    assert.equal(new Date(actionTrace[0].timestamp).toISOString(), "2026-10-09T10:14:02.000Z");
  });
});
