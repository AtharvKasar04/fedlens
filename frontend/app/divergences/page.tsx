import Link from "next/link";
import SeriesChart from "../../components/SeriesChart";

async function getDivergences() {
  try {
    const res = await fetch('http://127.0.0.1:8000/api/v1/divergences', { next: { revalidate: 60 } });
    if (!res.ok) return [];
    return await res.json();
  } catch (error) {
    console.error("Failed to fetch divergences:", error);
    return [];
  }
}

export default async function DivergencesPage() {
  const divergences = await getDivergences();
  const activeDivergences = divergences.filter((d: Record<string, unknown>) => d.is_divergent);

  return (
    <>
      <div className="page-header">
        <div className="page-breadcrumb">
          <Link href="/">Dashboard</Link>
          <span>›</span>
          Divergences
        </div>
        <h1 className="page-title">Narrative Divergences</h1>
        <div className="page-meta">
          <span className="badge badge-red">⚠ WATCHLIST</span>
          <span style={{ fontSize: 11, color: "#444" }}>
            Cases where Fed language contradicts actual FRED economic data
          </span>
        </div>
      </div>

      <div className="section-header" style={{ marginBottom: "var(--sp-4)" }}>
        <div className="section-title">
          <span>Detected Divergences</span> — Historical Analysis
        </div>
        <span className="badge badge-red">{activeDivergences.length} ACTIVE</span>
      </div>

      {activeDivergences.length === 0 ? (
        <div style={{ padding: "40px 20px", border: "1px solid var(--border-bright)", textAlign: "center", color: "#666", fontSize: 13 }}>
          No active divergences detected in the recent meetings.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--sp-8)", marginBottom: "var(--sp-8)" }}>
          {activeDivergences.map((divergence: Record<string, any>) => (
            <div
              key={divergence.id}
              style={{
                border: "1px solid var(--red)",
                background: "rgba(255,59,48,0.03)",
                overflow: "hidden",
              }}
            >
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 20px",
                  background: "rgba(255,59,48,0.06)",
                  borderBottom: "1px solid rgba(255,59,48,0.2)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span className="badge badge-grey">{divergence.meeting_date}</span>
                  <span className="badge badge-grey">{divergence.series_name}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="badge badge-red">{divergence.severity.toUpperCase()} SEVERITY</span>
                  <span className="badge badge-red">CONTRADICTION</span>
                </div>
              </div>

              {/* Body */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  borderBottom: "1px solid rgba(255,59,48,0.2)",
                }}
              >
                {/* Fed Claim */}
                <div
                  style={{
                    padding: "20px",
                    borderRight: "1px solid rgba(255,59,48,0.2)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.12em",
                      textTransform: "uppercase",
                      color: "var(--red)",
                      marginBottom: 12,
                    }}
                  >
                    ◀ FED CLAIM
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      color: "#FF8F8A",
                      fontStyle: "italic",
                      lineHeight: 1.7,
                      borderLeft: "3px solid var(--red)",
                      paddingLeft: 12,
                      marginBottom: 12,
                    }}
                  >
                    &quot;{divergence.fed_claim_text}&quot;
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="badge badge-red">{divergence.fed_claim_direction.toUpperCase()}</span>
                    <span style={{ fontSize: 11, color: "#555" }}>Direction stated by Fed</span>
                  </div>
                </div>

                {/* Actual Data */}
                <div style={{ padding: "20px" }}>
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.12em",
                      textTransform: "uppercase",
                      color: "var(--green)",
                      marginBottom: 12,
                    }}
                  >
                    ▶ ACTUAL DATA
                  </div>

                  {/* Data display */}
                  <div
                    style={{
                      display: "flex",
                      gap: 24,
                      marginBottom: 16,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>
                        Previous ({divergence.data_summary.previous_date})
                      </div>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 800,
                          fontFamily: "var(--font-mono)",
                          color: "#888",
                        }}
                      >
                        {divergence.data_summary.previous_value}
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: 24,
                        color: "#333",
                        display: "flex",
                        alignItems: "center",
                      }}
                    >
                      →
                    </div>
                    <div>
                      <div style={{ fontSize: 10, color: "#444", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>
                        Current ({divergence.data_summary.current_date})
                      </div>
                      <div
                        style={{
                          fontSize: 28,
                          fontWeight: 800,
                          fontFamily: "var(--font-mono)",
                          color: "var(--green)",
                        }}
                      >
                        {divergence.data_summary.current_value}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="badge badge-green">{divergence.data_direction.toUpperCase()}</span>
                    <span style={{ fontSize: 11, color: "#555" }}>Actual data trend</span>
                  </div>

                  <SeriesChart seriesName={divergence.series_name} meetingDate={divergence.meeting_date} />
                </div>
              </div>

              {/* LLM Explanation */}
              <div style={{ padding: "20px" }}>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    color: "#555",
                    marginBottom: 12,
                  }}
                >
                  AI EXPLANATION
                </div>
                <p style={{ fontSize: 13, color: "#888", lineHeight: 1.8, maxWidth: 800 }}>
                  {divergence.explanation}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info card */}
      <div
        style={{
          border: "1px solid var(--border-bright)",
          padding: "16px 20px",
          display: "flex",
          gap: 16,
          alignItems: "flex-start",
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "#444",
            paddingTop: 2,
            minWidth: 80,
          }}
        >
          NOTE
        </div>
        <p style={{ fontSize: 12, color: "#555", lineHeight: 1.7 }}>
          Divergences are automatically detected by FedLens analyzing the semantic meaning of the Fed&apos;s statement compared against the release dates of FRED macroeconomic indicators.
        </p>
      </div>
    </>
  );
}
