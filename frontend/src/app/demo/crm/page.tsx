"use client";

import React, { useState } from "react";

interface CustomerRecord {
  id: string;
  name: string;
  email: string;
  phone: string;
  company: string;
  status: "Active" | "Pending" | "Verified" | "VIP" | "Inactive";
  tier: string;
  notes: string;
  lastUpdated?: string;
}

const SEED_CUSTOMERS: CustomerRecord[] = [
  {
    id: "cust_101",
    name: "Rahul",
    email: "rahul@example.com",
    phone: "+1 (555) 234-8901",
    company: "Rahul Enterprises",
    status: "Active",
    tier: "Enterprise VIP",
    notes: "Awaiting verification document from email. Priority onboarding.",
    lastUpdated: "Today, 10:15 AM",
  },
  {
    id: "cust_102",
    name: "Priya Patel",
    email: "priya@example.org",
    phone: "+1 (555) 876-5432",
    company: "Apex Global",
    status: "Verified",
    tier: "Standard",
    notes: "Account verified. Active billing tier.",
    lastUpdated: "Yesterday",
  },
  {
    id: "cust_103",
    name: "Alex Johnson",
    email: "alex.j@example.com",
    phone: "+1 (555) 456-7890",
    company: "Nova Logic Inc",
    status: "Pending",
    tier: "Growth",
    notes: "Contract signed, pending tax documents.",
    lastUpdated: "Sep 24, 2026",
  },
];

export default function DemoCrmPage() {
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [hasSearched, setHasSearched] = useState<boolean>(false);
  const [matchedCustomer, setMatchedCustomer] = useState<CustomerRecord | null>(null);
  const [notFound, setNotFound] = useState<boolean>(false);

  // Editable customer form fields
  const [editName, setEditName] = useState<string>("");
  const [editEmail, setEditEmail] = useState<string>("");
  const [editCompany, setEditCompany] = useState<string>("");
  const [editStatus, setEditStatus] = useState<CustomerRecord["status"]>("Active");
  const [editTier, setEditTier] = useState<string>("");
  const [editNotes, setEditNotes] = useState<string>("");

  // Update confirmation state
  const [updateSuccess, setUpdateSuccess] = useState<boolean>(false);

  const handleSearch = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = searchQuery.trim().toLowerCase();
    setHasSearched(true);
    setUpdateSuccess(false);

    if (!query) {
      setMatchedCustomer(null);
      setNotFound(false);
      return;
    }

    // Deterministic failure condition: "Unknown Customer" or unseeded query
    if (query === "unknown customer" || query === "unknown") {
      setMatchedCustomer(null);
      setNotFound(true);
      return;
    }

    // Match customer by name (e.g. "Rahul") or email
    const found = SEED_CUSTOMERS.find(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.email.toLowerCase().includes(query)
    );

    if (found) {
      setMatchedCustomer(found);
      setNotFound(false);
      // Populate editable fields
      setEditName(found.name);
      setEditEmail(found.email);
      setEditCompany(found.company);
      setEditStatus(found.status);
      setEditTier(found.tier);
      setEditNotes(found.notes);
    } else {
      setMatchedCustomer(null);
      setNotFound(true);
    }
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!matchedCustomer) return;

    const updated: CustomerRecord = {
      ...matchedCustomer,
      name: editName,
      email: editEmail,
      company: editCompany,
      status: editStatus,
      tier: editTier,
      notes: editNotes,
      lastUpdated: "Just now",
    };

    setMatchedCustomer(updated);
    setUpdateSuccess(true);
  };

  return (
    <div className="space-y-6">
      {/* App Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-sky-950/80 border border-sky-800/80 text-sky-300 flex items-center justify-center shadow-md">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">WorkFlow CRM</h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/60">
                Demo CRM Application
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Customer relationship management console for search & record modification
            </p>
          </div>
        </div>

        {/* Workflow Action Helper */}
        <div className="flex items-center gap-2">
          <div className="text-right hidden sm:block">
            <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 block">Current Automation Step</span>
            <span className="text-xs font-mono font-medium text-cyan-300">
              search_customer → update_customer
            </span>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse hidden sm:block" />
        </div>
      </div>

      {/* Search Bar Section */}
      <section className="bg-zinc-900/50 border border-zinc-800/80 rounded-xl p-5 shadow-sm">
        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <label
                htmlFor="customer-search-input"
                className="block text-xs font-semibold text-zinc-300"
              >
                Search Customer
              </label>
              <div className="relative">
                <svg
                  className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  id="customer-search-input"
                  data-testid="customer-search"
                  type="text"
                  placeholder="Enter customer name or email (e.g. Rahul)..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg pl-9 pr-4 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-sans"
                />
              </div>
            </div>

            <button
              type="submit"
              data-testid="search-customer"
              id="search-customer-btn"
              className="px-5 py-2 rounded-lg text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-950 transition active:scale-95 cursor-pointer flex items-center justify-center gap-1.5 shrink-0"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Search Customer
            </button>
          </div>

          {/* Quick preset buttons for manual/automation testing */}
          <div className="flex items-center gap-2 pt-1 text-[11px] text-zinc-500">
            <span>Quick inputs:</span>
            <button
              type="button"
              onClick={() => {
                setSearchQuery("Rahul");
                setTimeout(() => {
                  const found = SEED_CUSTOMERS[0];
                  setHasSearched(true);
                  setNotFound(false);
                  setMatchedCustomer(found);
                  setEditName(found.name);
                  setEditEmail(found.email);
                  setEditCompany(found.company);
                  setEditStatus(found.status);
                  setEditTier(found.tier);
                  setEditNotes(found.notes);
                }, 50);
              }}
              className="text-cyan-400 hover:underline cursor-pointer font-mono"
            >
              &quot;Rahul&quot;
            </button>
            <span>•</span>
            <button
              type="button"
              onClick={() => {
                setSearchQuery("Unknown Customer");
                setHasSearched(true);
                setMatchedCustomer(null);
                setNotFound(true);
              }}
              className="text-rose-400 hover:underline cursor-pointer font-mono"
            >
              &quot;Unknown Customer&quot; (Phase 4.6 error test)
            </button>
          </div>
        </form>
      </section>

      {/* Customer Results / Record Viewer */}
      <section className="space-y-4">
        {/* 1. Deterministic Failure Condition: Customer Not Found */}
        {notFound && (
          <div
            data-testid="not-found-message"
            id="customer-not-found-alert"
            className="bg-rose-950/40 border border-rose-800/80 rounded-xl p-5 flex items-start gap-3.5 shadow-sm animate-fadeIn"
          >
            <div className="w-8 h-8 rounded-full bg-rose-500/20 text-rose-300 flex items-center justify-center shrink-0 mt-0.5">
              ✕
            </div>
            <div>
              <p className="text-sm font-bold text-rose-200">Customer not found</p>
              <p className="text-xs text-rose-300/80 mt-1">
                No customer record matches &quot;<span className="font-mono font-semibold">{searchQuery}</span>&quot; in the CRM database.
              </p>
              <p className="text-[11px] text-zinc-400 mt-2 font-mono">
                [Phase 4.6 trigger: human intervention fallback]
              </p>
            </div>
          </div>
        )}

        {/* 2. Customer Found Record Panel */}
        {matchedCustomer && (
          <div
            data-testid="customer-result"
            id="customer-record-card"
            className="bg-zinc-900/60 border border-zinc-800/80 rounded-xl p-6 shadow-sm space-y-6 animate-fadeIn"
          >
            {/* Customer Record Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-800">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-sky-600 via-indigo-600 to-purple-600 text-white font-bold font-mono text-lg flex items-center justify-center shadow-md">
                  {matchedCustomer.name.charAt(0)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2
                      data-testid="customer-name"
                      className="text-lg font-bold text-white tracking-tight"
                    >
                      {matchedCustomer.name}
                    </h2>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-950/70 text-emerald-300 border border-emerald-800/60">
                      {matchedCustomer.status}
                    </span>
                  </div>
                  <p
                    data-testid="customer-email"
                    className="text-xs text-zinc-400 font-mono mt-0.5"
                  >
                    {matchedCustomer.email}
                  </p>
                </div>
              </div>

              {/* Status Update Confirmation Banner */}
              {updateSuccess && (
                <div
                  data-testid="update-status"
                  id="customer-update-status"
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-950/70 text-emerald-200 border border-emerald-500/60 shadow-lg shadow-emerald-950/40 animate-fadeIn"
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>Customer updated ✓</span>
                </div>
              )}
            </div>

            {/* Editable Form for Automation */}
            <form onSubmit={handleUpdate} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Name */}
                <div className="space-y-1">
                  <label htmlFor="edit-name" className="block text-xs font-semibold text-zinc-300">
                    Customer Name
                  </label>
                  <input
                    id="edit-name"
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-cyan-500 font-sans"
                    required
                  />
                </div>

                {/* Email */}
                <div className="space-y-1">
                  <label htmlFor="edit-email" className="block text-xs font-semibold text-zinc-300">
                    Customer Email
                  </label>
                  <input
                    id="edit-email"
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-cyan-500 font-mono"
                    required
                  />
                </div>

                {/* Company */}
                <div className="space-y-1">
                  <label htmlFor="edit-company" className="block text-xs font-semibold text-zinc-300">
                    Company
                  </label>
                  <input
                    id="edit-company"
                    type="text"
                    value={editCompany}
                    onChange={(e) => setEditCompany(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-cyan-500 font-sans"
                  />
                </div>

                {/* Status */}
                <div className="space-y-1">
                  <label htmlFor="edit-status" className="block text-xs font-semibold text-zinc-300">
                    Account Status
                  </label>
                  <select
                    id="edit-status"
                    data-testid="customer-status"
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value as CustomerRecord["status"])}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-cyan-500 cursor-pointer font-sans"
                  >
                    <option value="Active">Active</option>
                    <option value="Verified">Verified</option>
                    <option value="VIP">VIP</option>
                    <option value="Pending">Pending</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>

                {/* Tier */}
                <div className="space-y-1">
                  <label htmlFor="edit-tier" className="block text-xs font-semibold text-zinc-300">
                    Service Tier
                  </label>
                  <input
                    id="edit-tier"
                    data-testid="customer-tier"
                    type="text"
                    value={editTier}
                    onChange={(e) => setEditTier(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-100 focus:outline-none focus:border-cyan-500 font-sans"
                  />
                </div>

                {/* Phone */}
                <div className="space-y-1">
                  <label htmlFor="edit-phone" className="block text-xs font-semibold text-zinc-300">
                    Contact Phone
                  </label>
                  <input
                    id="edit-phone"
                    type="text"
                    defaultValue={matchedCustomer.phone}
                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-400 font-mono"
                  />
                </div>
              </div>

              {/* Notes */}
              <div className="space-y-1">
                <label htmlFor="edit-notes" className="block text-xs font-semibold text-zinc-300">
                  Verification / CRM Notes
                </label>
                <textarea
                  id="edit-notes"
                  data-testid="customer-notes"
                  rows={3}
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-100 focus:outline-none focus:border-cyan-500 font-sans leading-relaxed"
                />
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-between">
                <span className="text-[11px] text-zinc-500 font-mono">
                  Record ID: {matchedCustomer.id}
                </span>

                <button
                  type="submit"
                  data-testid="update-customer"
                  id="update-customer-btn"
                  className="px-5 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white shadow-md shadow-sky-950/60 active:scale-95 transition cursor-pointer"
                >
                  Update Customer
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Initial Empty State before searching */}
        {!hasSearched && (
          <div className="py-16 text-center bg-zinc-900/30 border border-zinc-800/60 rounded-xl p-8">
            <div className="w-12 h-12 rounded-xl bg-zinc-800/60 border border-zinc-700/60 flex items-center justify-center mx-auto text-zinc-400 mb-3">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </div>
            <h3 className="text-sm font-semibold text-zinc-200">Ready for Customer Search</h3>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto mt-1">
              Search for <strong className="text-zinc-300">Rahul</strong> to inspect and update the customer record, or search <strong className="text-zinc-300">Unknown Customer</strong> to test intervention fallback.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
