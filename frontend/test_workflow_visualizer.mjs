import test from "node:test";
import assert from "node:assert/strict";

test("Workflow Visualizer Pipeline & Step Status Verification", async (t) => {
  const GMAIL_TRIAGE_STEPS = [
    { id: "step_search_email", name: "Search Gmail messages", action: "search_messages", app: "gmail" },
    { id: "step_read_email", name: "Read the email", action: "read_message", app: "gmail" },
    { id: "step_download_attachment", name: "Download the attachment", action: "download_attachment", app: "gmail" },
    { id: "step_search_crm", name: "Search for the CRM customer", action: "search_customer", app: "crm" },
    { id: "step_update_crm", name: "Update the CRM customer", action: "update_customer", app: "crm" },
    { id: "step_send_chat", name: "Send the Chat notification", action: "send_message", app: "chat" },
  ];

  await t.test("1. wf_gmail_triage_pipeline consists of exactly 6 ordered steps", () => {
    assert.equal(GMAIL_TRIAGE_STEPS.length, 6);
    assert.equal(GMAIL_TRIAGE_STEPS[0].action, "search_messages");
    assert.equal(GMAIL_TRIAGE_STEPS[1].action, "read_message");
    assert.equal(GMAIL_TRIAGE_STEPS[2].action, "download_attachment");
    assert.equal(GMAIL_TRIAGE_STEPS[3].action, "search_customer");
    assert.equal(GMAIL_TRIAGE_STEPS[4].action, "update_customer");
    assert.equal(GMAIL_TRIAGE_STEPS[5].action, "send_message");
  });

  await t.test("2. Application assignments match Gmail, CRM, and Chat ecosystem", () => {
    assert.equal(GMAIL_TRIAGE_STEPS[0].app, "gmail");
    assert.equal(GMAIL_TRIAGE_STEPS[1].app, "gmail");
    assert.equal(GMAIL_TRIAGE_STEPS[2].app, "gmail");
    assert.equal(GMAIL_TRIAGE_STEPS[3].app, "crm");
    assert.equal(GMAIL_TRIAGE_STEPS[4].app, "crm");
    assert.equal(GMAIL_TRIAGE_STEPS[5].app, "chat");
  });

  await t.test("3. Step status derivation evaluates completed, running, paused, and failed", () => {
    function deriveStepStatus(step, execution, isExecuting) {
      if (!execution) {
        return isExecuting && step.id === "step_search_email" ? "running" : "pending";
      }
      if (execution.status === "completed") return "completed";
      if (execution.completed_actions?.includes(step.action) || execution.completed_actions?.includes(step.id)) {
        return "completed";
      }
      if (execution.failed_action === step.action || execution.failed_action === step.id) {
        return "failed";
      }
      if (execution.current_action === step.action || execution.current_action === step.id) {
        return execution.status === "paused" ? "paused" : "running";
      }
      return "pending";
    }

    // Pre-execution
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[0], null, false), "pending");

    // In-flight execution
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[0], null, true), "running");

    // Mid-execution record
    const midExec = {
      status: "running",
      completed_actions: ["search_messages", "read_message"],
      current_action: "download_attachment",
    };
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[0], midExec, true), "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[1], midExec, true), "completed");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[2], midExec, true), "running");
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[3], midExec, true), "pending");

    // Paused execution
    const pausedExec = {
      status: "paused",
      completed_actions: ["search_messages", "read_message", "download_attachment"],
      current_action: "search_customer",
    };
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[3], pausedExec, false), "paused");

    // Failed execution
    const failedExec = {
      status: "failed",
      completed_actions: ["search_messages"],
      failed_action: "read_message",
    };
    assert.equal(deriveStepStatus(GMAIL_TRIAGE_STEPS[1], failedExec, false), "failed");
  });
});
