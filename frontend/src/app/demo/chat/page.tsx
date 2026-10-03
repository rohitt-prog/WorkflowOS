"use client";

import React, { useState } from "react";

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
  };

  return (
    <div className="space-y-6">
      {/* App Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-950/80 border border-emerald-800/80 text-emerald-300 flex items-center justify-center shadow-md">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">WorkFlow Chat</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
                Demo Team Messaging
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Simulated enterprise team messaging client for Playwright automation
            </p>
          </div>
        </div>

        {/* Workflow Action Helper */}
        <div className="flex items-center gap-2">
          <div className="text-right hidden sm:block">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">Current Automation Step</span>
            <span className="text-xs font-mono font-medium text-cyan-300">
              send_message → #customer-support
            </span>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse hidden sm:block" />
        </div>
      </div>

      {/* Main Chat Layout (Channels Sidebar + Conversation Area) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[550px]">
        {/* Channels Sidebar */}
        <aside className="lg:col-span-3 space-y-4">
          <div className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-3 space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 px-3 py-1 block">
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
                      ? "bg-emerald-950/60 text-emerald-200 border border-emerald-800/60"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-zinc-500">#</span>
                    <span>{ch.name.replace("#", "")}</span>
                  </div>
                  {ch.count > 0 && (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400">
                      {ch.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Quick Guidance Box */}
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3.5 text-xs font-sans space-y-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-semibold block">
              Playwright Target
            </span>
            <p className="text-zinc-400 text-[11px] leading-relaxed">
              Verify channel is <strong className="text-white">{selectedChannel}</strong>, type notification into{" "}
              <code className="text-cyan-300 bg-zinc-900 px-1 py-0.5 rounded font-mono">data-testid=&quot;message-input&quot;</code>,
              and trigger{" "}
              <code className="text-cyan-300 bg-zinc-900 px-1 py-0.5 rounded font-mono">data-testid=&quot;send-message&quot;</code>.
            </p>
          </div>
        </aside>

        {/* Chat Conversation Area */}
        <section className="lg:col-span-9 bg-zinc-900/50 border border-zinc-800/80 rounded-xl overflow-hidden shadow-sm flex flex-col justify-between">
          {/* Channel Header Bar */}
          <div className="px-5 py-3.5 border-b border-zinc-800/80 bg-zinc-900/30 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <h2
                data-testid="chat-channel"
                className="text-sm font-bold text-white font-mono"
              >
                {selectedChannel}
              </h2>
              <span className="text-xs text-zinc-500 hidden sm:inline">• Customer onboarding and verification notifications</span>
            </div>

            {/* Notification / Sent Status Banner */}
            {sendSuccess && (
              <span
                data-testid="send-status"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-300 bg-emerald-950/60 border border-emerald-800/80 px-2.5 py-0.5 rounded-full animate-fadeIn"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Message sent ✓
              </span>
            )}
          </div>

          {/* Message List */}
          <div
            data-testid="message-list"
            id="chat-messages-container"
            className="p-5 space-y-4 overflow-y-auto flex-1 max-h-[420px]"
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                data-testid={msg.isCurrentUser ? "sent-message" : undefined}
                className={`flex items-start gap-3 p-3 rounded-xl transition ${
                  msg.isCurrentUser
                    ? "bg-indigo-950/30 border border-indigo-900/40 ml-4 sm:ml-12"
                    : "bg-zinc-900/40 border border-zinc-800/40 mr-4 sm:mr-12"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${
                    msg.isCurrentUser
                      ? "bg-indigo-600 text-white shadow-sm shadow-indigo-900"
                      : "bg-zinc-800 text-zinc-200 border border-zinc-700"
                  }`}
                >
                  {msg.avatar}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-white">
                      {msg.sender}
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono">
                      {msg.timestamp}
                    </span>
                    {msg.isCurrentUser && (
                      <span className="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-indigo-900/60 text-indigo-300">
                        You
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-zinc-200 mt-1 leading-relaxed break-words font-sans">
                    {msg.content}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Message Input Form */}
          <form
            onSubmit={handleSendMessage}
            className="p-4 border-t border-zinc-800/80 bg-zinc-950/80 space-y-2"
          >
            <div className="flex items-center justify-between">
              <label
                htmlFor="chat-message-input"
                className="text-xs font-semibold text-zinc-300"
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
                className="text-[11px] text-cyan-400 hover:underline cursor-pointer font-mono"
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
                className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-sans"
              />
              <button
                type="submit"
                data-testid="send-message"
                id="send-message-btn"
                disabled={!inputText.trim()}
                className="px-5 py-2 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-950 disabled:opacity-40 disabled:cursor-not-allowed transition active:scale-95 cursor-pointer flex items-center gap-1.5 shrink-0"
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
