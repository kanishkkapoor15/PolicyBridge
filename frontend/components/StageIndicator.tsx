"use client";

const stages = [
  { key: "initialization", label: "Setup" },
  { key: "batch_analysis", label: "Analysis" },
  { key: "document_conversion", label: "Conversion" },
  { key: "session_summary", label: "Summary" },
];

export default function StageIndicator({ currentStage }: { currentStage: string }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {stages.map((stage, i) => (
        <div key={stage.key} className="flex items-center">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              stage.key === currentStage
                ? "bg-blue-600 text-white"
                : "bg-gray-200 text-gray-600"
            }`}
          >
            {i + 1}
          </div>
          <span className="ml-2 text-sm text-gray-700">{stage.label}</span>
          {i < stages.length - 1 && <div className="w-8 h-px bg-gray-300 mx-2" />}
        </div>
      ))}
    </div>
  );
}
