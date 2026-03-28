import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <div className="max-w-4xl mx-auto px-6 py-20">
        <h1 className="text-5xl font-bold text-slate-900 mb-4">PolicyBridge</h1>
        <p className="text-xl text-slate-600 mb-8">
          Agentic compliance conversion platform — migrate company policies to
          Irish &amp; EU law compliance with AI-powered analysis and guided review.
        </p>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 mb-8">
          <h2 className="text-2xl font-semibold text-slate-800 mb-4">How it works</h2>
          <ol className="space-y-3 text-slate-600">
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">1</span>
              <span>Select policy category and source jurisdiction, then upload documents</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">2</span>
              <span>AI agents analyze your batch — flag conflicts, identify compliance gaps</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">3</span>
              <span>Review and approve the conversion plan, then guide document-by-document conversion</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-7 h-7 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">4</span>
              <span>Export fully compliant documents with audit trail and compliance citations</span>
            </li>
          </ol>
        </div>
        <Link
          href="/session/new"
          className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Start New Session
        </Link>
      </div>
    </main>
  );
}
