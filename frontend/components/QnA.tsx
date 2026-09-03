'use client';

import { useState } from 'react';

export default function QnA() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, any> | null>(null);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setResult(null);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: query, top_k: 3 }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      setResult({ answer: "Failed to connect to the RAG API.", sources: [] });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ marginTop: "var(--sp-8)", border: "1px solid var(--border-bright)" }}>
      <div className="card-header">
        <div className="card-title">Ask FedLens (RAG)</div>
        <div className="badge badge-grey">AI SEARCH</div>
      </div>
      
      <form onSubmit={handleAsk} style={{ display: "flex", gap: "var(--sp-2)", marginBottom: "var(--sp-4)" }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about FOMC statements..."
          style={{
            flex: 1,
            background: "var(--surface-2)",
            border: "1px solid var(--border-bright)",
            color: "var(--white)",
            padding: "12px 16px",
            fontFamily: "var(--font-mono)",
            fontSize: 14,
            outline: "none"
          }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            background: "var(--white)",
            color: "var(--black)",
            border: "none",
            padding: "0 24px",
            fontWeight: 800,
            textTransform: "uppercase",
            fontFamily: "var(--font-sans)",
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.7 : 1
          }}
        >
          {loading ? "SEARCHING..." : "ASK"}
        </button>
      </form>

      {result && (
        <div style={{ padding: "var(--sp-4)", background: "var(--surface-2)", border: "1px solid var(--border-bright)" }}>
          <div style={{ fontSize: 11, color: "var(--green)", fontWeight: 700, letterSpacing: "0.1em", marginBottom: "var(--sp-2)" }}>
            ▶ ANSWER
          </div>
          <div style={{ fontSize: 14, lineHeight: 1.7, marginBottom: "var(--sp-4)" }}>
            {result.answer}
          </div>
          
          {result.sources && result.sources.length > 0 && (
            <>
              <div style={{ fontSize: 11, color: "#8F8F8F", fontWeight: 700, letterSpacing: "0.1em", marginBottom: "var(--sp-2)", marginTop: "var(--sp-4)" }}>
                SOURCES
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-2)" }}>
                {result.sources.map((s: Record<string, any>, idx: number) => (
                  <div key={idx} style={{ fontSize: 12, color: "#A3A3A3", padding: "8px", borderLeft: "2px solid var(--border-bright)", background: "var(--surface)" }}>
                    <span style={{ color: "var(--white)", marginRight: 8 }}>[{s.meeting_date}]</span>
                    {s.text.substring(0, 150)}...
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
