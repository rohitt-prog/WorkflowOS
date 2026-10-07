"use client";

import React, { useState } from "react";
import { emitActivityEvent } from "@/lib/api";

interface ChatMessage {
  id: string;
  sender: string;
  avatar: string;
  timestamp: string;
  content: string;
  isCurrentUser?: boolean;
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "msg_1",
    sender: "Support Bot",
    avatar: "🤖",
    timestamp: "10:00 AM",
    content: "Welcome to #customer-support. Automated notifications and customer updates are posted here.",
    isCurrentUser: false,
  },
  {
    id: "msg_2",
    sender: "Alex (Support)",
    avatar: "A",
    timestamp: "10:15 AM",
    content: "Standing by for customer verification requests. Let me know once customer Rahul is updated in CRM.",
    isCurrentUser: false,
  },
];

const CHANNELS = [
  { id: "customer-support", name: "#customer-support", active: true, count: 2 },
  { id: "ops-alerts", name: "#ops-alerts", active: false, count: 0 },
  { id: "general", name: "#general", active: false, count: 5 },
];

export default function DemoChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [inputText, setInputText] = useState<string>("");
  const [selectedChannel, setSelectedChannel] = useState<string>("#customer-support");
  const [sendSuccess, setSendSuccess] = useState<boolean>(false);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    const text = inputText.trim();
    if (!text) return;

    const newMessage: ChatMessage = {
      id: `msg_${Date.now()}`,
      sender: "WorkFlow Operator",
      avatar: "W",
      timestamp: "Just now",
      content: text,
      isCurrentUser: true,
    };

    setMessages((prev) => [...prev, newMessage]);
    setInputText("");
    setSendSuccess(true);

    void emitActivityEvent({
      application: "demo_chat",
      event_type: "send_message",
      target: "customer_request",
      metadata: {
        channel: selectedChannel,
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* App Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#E2E8F0] rounded-xl p-5 shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-[#0F172A] tracking-tight">WorkFlow Chat</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                Demo Team Messaging
              </span>
            </div>
            <p className="text-xs text-[#64748B] mt-0.5">
              Simulated internal team communication channel targeted by Playwright automation (Step 5)
            </p>
          </div>
        </div>

        {/* Current Automation Step Indicator */}
        <div className="flex items-center gap-2 self-start sm:self-auto bg-[#F8FAFC] border border-[#E2E8F0] px-3 py-1.5 rounded-lg text-xs">
          <span className="w-2 h-2 rounded-full bg-[#16A34A] animate-pulse" />
          <span className="text-[#64748B] font-medium">Workflow Action:</span>
          <span className="font-mono text-[#0F172A] font-semibold">send_message → #customer-support</span>
        </div>
      </div>

      {/* Main Chat Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[550px]">
        {/* Channels Sidebar */}
        <aside className="lg:col-span-3 space-y-4">
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-3 space-y-1 shadow-2xs">
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#94A3B8] px-3 py-1 block">
              Channels
            </span>
            {CHANNELS.map((ch) => {
              const isSelected = selectedChannel === ch.name;
              return (
                <button
                  key={ch.id}
                  data-testid="chat-channel"
                  id={`channel-${ch.id}`}
                  onClick={() => setSelectedChannel(ch.name)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition cursor-pointer ${
                    isSelected
                      ? "bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold"
                      : "text-[#475569] hover:bg-[#F8FAFC]"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[#94A3B8]">#</span>
                    <span>{ch.name.replace("#", "")}</span>
                  </div>
                  {ch.count > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#F1F5F9] text-[#64748B]">
                      {ch.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Guidance Box */}
          <div className="bg-white border border-[#E2E8F0] rounded-xl p-4 text-xs space-y-1.5 shadow-2xs">
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#16A34A] font-bold block">
              Automation Target
            </span>
            <p className="text-[#64748B] text-[11px] leading-relaxed">
              Verify channel is <strong className="text-[#0F172A]">{selectedChannel}</strong>, type notification into{" "}
              <code className="text-[#1D4ED8] bg-blue-50 px-1 py-0.5 rounded font-mono">data-testid=&quot;message-input&quot;</code>,
              and trigger{" "}
              <code className="text-[#1D4ED8] bg-blue-50 px-1 py-0.5 rounded font-mono">data-testid=&quot;send-message&quot;</code>.
            </p>
          </div>
        </aside>

        {/* Chat Conversation Area */}
        <section className="lg:col-span-9 bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-2xs flex flex-col justify-between">
          {/* Channel Header Bar */}
          <div className="px-5 py-3.5 border-b border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#16A34A]" />
              <h2
                data-testid="chat-channel"
                className="text-xs font-bold text-[#0F172A] font-mono"
              >
                {selectedChannel}
              </h2>
              <span className="text-xs text-[#64748B] hidden sm:inline">• Customer onboarding and verification notifications</span>
            </div>

            {/* Notification / Sent Status Banner */}
            {sendSuccess && (
              <span
                data-testid="send-status"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 rounded-full animate-fadeIn"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] animate-pulse" />
                Message sent ✓
              </span>
            )}
          </div>

          {/* Message List */}
          <div
            data-testid="message-list"
            id="chat-messages-container"
            className="p-5 space-y-3.5 overflow-y-auto flex-1 max-h-[420px]"
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                data-testid={msg.isCurrentUser ? "sent-message" : undefined}
                className={`flex items-start gap-3 p-3.5 rounded-xl transition ${
                  msg.isCurrentUser
                    ? "bg-[#EFF6FF] border border-[#BFDBFE] ml-4 sm:ml-12"
                    : "bg-[#F8FAFC] border border-[#E2E8F0] mr-4 sm:mr-12"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${
                    msg.isCurrentUser
                      ? "bg-[#2563EB] text-white"
                      : "bg-white text-[#0F172A] border border-[#E2E8F0]"
                  }`}
                >
                  {msg.avatar}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[#0F172A]">
                      {msg.sender}
                    </span>
                    <span className="text-[10px] text-[#94A3B8] font-mono">
                      {msg.timestamp}
                    </span>
                    {msg.isCurrentUser && (
                      <span className="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-blue-100 text-[#1D4ED8] font-bold">
                        Operator
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[#334155] mt-1 leading-relaxed break-words font-sans">
                    {msg.content}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Message Input Form */}
          <form
            onSubmit={handleSendMessage}
            className="p-4 border-t border-[#E2E8F0] bg-[#F8FAFC] space-y-2"
          >
            <div className="flex items-center justify-between">
              <label
                htmlFor="chat-message-input"
                className="text-xs font-semibold text-[#0F172A]"
              >
                Send message to {selectedChannel}
              </label>

              {/* Sample Preset Button for quick filling */}
              <button
                type="button"
                onClick={() =>
                  setInputText(
                    "Customer Rahul record updated in CRM with VIP tier. Request document verified."
                  )
                }
                className="text-[11px] text-[#2563EB] hover:underline cursor-pointer font-mono font-medium"
              >
                Insert sample notification
              </button>
            </div>

            <div className="flex items-center gap-2">
              <input
                id="chat-message-input"
                data-testid="message-input"
                type="text"
                placeholder="Type your message to the support team..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="flex-1 bg-white border border-[#E2E8F0] rounded-lg px-3.5 py-2 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#2563EB] font-sans"
              />
              <button
                type="submit"
                data-testid="send-message"
                id="send-message-btn"
                disabled={!inputText.trim()}
                className="px-5 py-2 rounded-lg text-xs font-semibold bg-[#16A34A] hover:bg-[#15803D] text-white shadow-2xs disabled:opacity-40 disabled:cursor-not-allowed transition active:scale-97 cursor-pointer flex items-center gap-1.5 shrink-0"
              >
                <span>Send</span>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
