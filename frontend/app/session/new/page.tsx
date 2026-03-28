"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const categories = [
  { value: "hr_employment", label: "HR / Employment" },
  { value: "data_protection", label: "Data Protection" },
  { value: "it_security", label: "IT / Security" },
  { value: "corporate_governance", label: "Corporate Governance" },
  { value: "health_safety", label: "Health & Safety" },
];

const jurisdictions = [
  { value: "us_delaware", label: "US - Delaware" },
  { value: "us_california", label: "US - California" },
  { value: "us_federal", label: "US - Federal" },
  { value: "us_new_york", label: "US - New York" },
  { value: "uk", label: "United Kingdom" },
];

export default function NewSession() {
  const router = useRouter();
  const [category, setCategory] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");

  return (
    <main className="min-h-screen bg-slate-50 py-12">
      <div className="max-w-2xl mx-auto px-6">
        <h1 className="text-3xl font-bold text-slate-900 mb-8">New Compliance Session</h1>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Policy Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-slate-900"
            >
              <option value="">Select a category...</option>
              {categories.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Source Jurisdiction
            </label>
            <select
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 text-slate-900"
            >
              <option value="">Select source jurisdiction...</option>
              {jurisdictions.map((j) => (
                <option key={j.value} value={j.value}>{j.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Upload Policy Documents
            </label>
            <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center">
              <p className="text-slate-500 text-sm">
                Upload functionality — to be implemented in step 7
              </p>
              <p className="text-slate-400 text-xs mt-1">Supports PDF and Word documents</p>
            </div>
          </div>
          <button
            disabled={!category || !jurisdiction}
            className="w-full bg-blue-600 text-white rounded-lg px-4 py-2.5 font-medium hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
          >
            Create Session &amp; Start Analysis
          </button>
        </div>
      </div>
    </main>
  );
}
