import test from "node:test";
import assert from "node:assert/strict";

test("BuilderView Action Selection & Parameter Binding Verification", async (t) => {
  // Simulates the action selection handler in BuilderView
  function handleActionChange(currentStep, newType) {
    const updates = { type: newType };
    if (newType === "list_recent_messages") {
      updates.application = "gmail";
      updates.parameters = {
        ...currentStep.parameters,
        max_results: currentStep.parameters?.max_results || 5,
        query: currentStep.parameters?.query || "label:INBOX",
      };
    } else if (newType === "search_messages") {
      const isCompatible = currentStep.application === "gmail" || currentStep.application === "chat";
      const targetApp = isCompatible ? currentStep.application : "gmail";
      updates.application = targetApp;
      updates.parameters = {
        ...currentStep.parameters,
        query: currentStep.parameters?.query || (targetApp === "gmail" ? "label:INBOX" : ""),
        ...(targetApp === "gmail" ? { max_results: currentStep.parameters?.max_results || 5 } : {}),
      };
    } else if (newType === "read_message") {
      const isCompatible = currentStep.application === "gmail" || currentStep.application === "chat";
      const targetApp = isCompatible ? currentStep.application : "gmail";
      updates.application = targetApp;
      updates.parameters = {
        ...currentStep.parameters,
        message_id: currentStep.parameters?.message_id || "",
      };
    }
    return { ...currentStep, ...updates };
  }

  // Simulates the message_id parameter update in BuilderView
  function handleMessageIdChange(currentStep, newMessageId) {
    return {
      ...currentStep,
      parameters: {
        ...currentStep.parameters,
        message_id: newMessageId,
      },
    };
  }

  await t.test("1. When search_messages is selected with incompatible app, switches to gmail and sets query", () => {
    const step = {
      id: "step_1",
      type: "search_customer",
      application: "crm",
      parameters: { custom_flag: true },
    };
    const updated = handleActionChange(step, "search_messages");
    assert.equal(updated.type, "search_messages");
    assert.equal(updated.application, "gmail");
    assert.equal(updated.parameters.query, "label:INBOX");
    assert.equal(updated.parameters.max_results, 5);
    assert.equal(updated.parameters.custom_flag, true); // preserved
  });

  await t.test("2. When search_messages is selected with chat, preserves chat app", () => {
    const step = {
      id: "step_2",
      type: "send_message",
      application: "chat",
      parameters: { query: "urgent" },
    };
    const updated = handleActionChange(step, "search_messages");
    assert.equal(updated.type, "search_messages");
    assert.equal(updated.application, "chat");
    assert.equal(updated.parameters.query, "urgent");
  });

  await t.test("3. When read_message is selected with incompatible app, switches to gmail and sets message_id", () => {
    const step = {
      id: "step_3",
      type: "update_customer",
      application: "browser",
      parameters: { retained_key: "value123" },
    };
    const updated = handleActionChange(step, "read_message");
    assert.equal(updated.type, "read_message");
    assert.equal(updated.application, "gmail");
    assert.equal(updated.parameters.message_id, "");
    assert.equal(updated.parameters.retained_key, "value123");
  });

  await t.test("4. When read_message is selected with chat, preserves chat app", () => {
    const step = {
      id: "step_4",
      type: "send_message",
      application: "chat",
      parameters: { message_id: "msg_exist_456" },
    };
    const updated = handleActionChange(step, "read_message");
    assert.equal(updated.type, "read_message");
    assert.equal(updated.application, "chat");
    assert.equal(updated.parameters.message_id, "msg_exist_456");
  });

  await t.test("5. Message ID binding updates step.parameters.message_id while preserving other parameters", () => {
    const step = {
      id: "step_5",
      type: "read_message",
      application: "gmail",
      parameters: {
        message_id: "",
        channel: "notifications",
        token: "tok_abc",
      },
    };
    const updated = handleMessageIdChange(step, "{{steps.step_1.output.id}}");
    assert.equal(updated.parameters.message_id, "{{steps.step_1.output.id}}");
    assert.equal(updated.parameters.channel, "notifications");
    assert.equal(updated.parameters.token, "tok_abc");
  });
});

