import Link from "next/link";
import { getMeetingDetail } from "@/lib/api";

function gradeToClass(grade: string | undefined): string {
  if (!grade) return "grey";
  const g = grade.toLowerCase();
  if (g === "improving" || g === "dovish") return "green";
  if (g === "deteriorating" || g === "hawkish") return "red";
  if (g === "stable") return "amber";
  return "blue";
}

function renderDiff(rawDiff: string) {
  if (!rawDiff) return null;
  const parts = rawDiff.split(/(\[ADDED\].*?\[\/ADDED\]|\[DELETED\].*?\[\/DELETED\])/gs);
  
  return parts.map((part, i) => {
    if (part.startsWith('[ADDED]')) {
      const text = part.replace('[ADDED]', '').replace('[/ADDED]', '');
      return <span key={i} style={{ backgroundColor: 'rgba(52, 199, 89, 0.2)', color: 'var(--green)', padding: '0 2px', borderRadius: 2 }}>{text}</span>;
    }
    if (part.startsWith('[DELETED]')) {
      const text = part.replace('[DELETED]', '').replace('[/DELETED]', '');
      return <span key={i} style={{ backgroundColor: 'rgba(255, 59, 48, 0.2)', color: 'var(--red)', padding: '0 2px', textDecoration: 'line-through', borderRadius: 2 }}>{text}</span>;
    }
    return <span key={i}>{part}</span>;
  });
}

const DIMENSION_LABELS: Record<string, string> = {
  inflation: "Inflation",
  labor_market: "Labor Market",
  economic_growth: "Economic Growth",
  financial_conditions: "Financial Conditions",
  forward_guidance: "Forward Guidance",
};

export default async function MeetingDetailPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  let detail = null;
  let error = false;

  try {
    detail = await getMeetingDetail(date);
  } catch {
    error = true;
  }

  const assessment = detail?.assessment;
  const changeDetection = detail?.change_detection;
  const stance = assessment?.overall_stance;

  const dimensions = assessment
    ? Object.entries(DIMENSION_LABELS)
        .map(([key, label]) => ({
          key,
          label,
          data: assessment[key as keyof typeof assessment] as
            | { grade: string; evidence: string }
            | undefined,
        }))
        .filter((d) => d.data)
    : [];

  return (
    <>
      {/* Breadcrumb + Title */}
      <div className="page-header">
        <div className="page-breadcrumb">
          <Link href="/">Dashboard</Link>
          <span>›</span>
          FOMC Meeting
        </div>
        <h1 className="page-title">{date}</h1>
        <div className="page-meta">
          <span className="badge badge-grey">FOMC STATEMENT</span>
          {stance && (
            <span className={`badge badge-${gradeToClass(stance.grade)}`}>
              {stance.grade.toUpperCase()}
            </span>
          )}
          {changeDetection?.hawkish_or_dovish && (
            <span
              className={`badge badge-${gradeToClass(changeDetection.hawkish_or_dovish)}`}
            >
              SHIFT: {changeDetection.hawkish_or_dovish.toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="empty">
          <div className="empty-icon">⚠</div>
          <div className="empty-title">Could not load meeting data</div>
          <div className="empty-sub">Ensure the API server is running.</div>
        </div>
      )}

      {!error && !assessment && (
        <div className="empty">
          <div className="empty-icon">◻</div>
          <div className="empty-title">No Analysis Available</div>
          <div className="empty-sub">
            Run the analysis pipeline:{" "}
            <code>uv run python -m app.analysis.pipeline</code>
          </div>
        </div>
      )}

      {assessment && (
        <>
          {/* Stance Hero + Change Detection Summary */}
          <div className="grid-2" style={{ marginBottom: "var(--sp-8)", alignItems: "stretch" }}>
            {/* Stance hero */}
            <div
              className="stance-hero"
              data-stance={stance?.grade ?? ""}
            >
              <div className="stance-label">Overall Policy Stance</div>
              <div className={`stance-value ${gradeToClass(stance?.grade)}`}>
                {stance?.grade?.toUpperCase() ?? "UNKNOWN"}
              </div>
              {stance?.evidence && (
                <p
                  style={{
                    fontSize: 12,
                    color: "#555",
                    marginTop: "var(--sp-5)",
                    fontStyle: "italic",
                    lineHeight: 1.7,
                    maxWidth: 480,
                    margin: "var(--sp-5) auto 0",
                  }}
                >
                  &quot;{stance.evidence}&quot;
                </p>
              )}
            </div>

            {/* Change detection summary */}
            <div className="card" style={{ height: "100%" }}>
              <div className="card-header">
                <div className="card-title">Policy Shift Detection</div>
                {changeDetection?.hawkish_or_dovish && (
                  <span
                    className={`badge badge-${gradeToClass(changeDetection.hawkish_or_dovish)}`}
                  >
                    {changeDetection.hawkish_or_dovish.toUpperCase()}
                  </span>
                )}
              </div>

              {changeDetection ? (
                <>
                  {changeDetection.key_takeaway && (
                    <p
                      style={{
                        fontSize: 12,
                        color: "#bbb",
                        lineHeight: 1.75,
                        marginBottom: "var(--sp-5)",
                      }}
                    >
                      {changeDetection.key_takeaway}
                    </p>
                  )}
                  {changeDetection.summary_of_changes && (
                    <div
                      style={{
                        fontSize: 11,
                        color: "#555",
                        lineHeight: 1.7,
                        borderTop: "1px solid var(--border)",
                        paddingTop: "var(--sp-4)",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          letterSpacing: "0.1em",
                          textTransform: "uppercase",
                          color: "#333",
                          display: "block",
                          marginBottom: 6,
                        }}
                      >
                        Full Summary
                      </span>
                      {changeDetection.summary_of_changes}
                    </div>
                  )}
                  {changeDetection.text_diff?.raw_diff && (
                    <div
                      style={{
                        fontSize: 11,
                        color: "#888",
                        lineHeight: 1.8,
                        borderTop: "1px solid var(--border)",
                        paddingTop: "var(--sp-4)",
                        marginTop: "var(--sp-4)",
                        fontFamily: "var(--font-mono)",
                        maxHeight: "300px",
                        overflowY: "auto",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          letterSpacing: "0.1em",
                          textTransform: "uppercase",
                          color: "#333",
                          display: "block",
                          marginBottom: 6,
                          fontFamily: "var(--font-sans)",
                        }}
                      >
                        Exact Text Diff
                      </span>
                      {renderDiff(changeDetection.text_diff.raw_diff)}
                    </div>
                  )}
                </>
              ) : (
                <span style={{ fontSize: 12, color: "#444" }}>
                  No comparison available — earliest meeting in database.
                </span>
              )}
            </div>
          </div>

          {/* Policy Dimensions */}
          <div className="section-header">
            <div className="section-title">
              <span>Policy Dimensions</span> — AI-extracted, evidence-backed
            </div>
          </div>

          <div
            className="dimension-grid"
            style={{ marginBottom: "var(--sp-8)" }}
          >
            {dimensions.map(({ key, label, data }) => (
              <div
                key={key}
                className={`dimension-card ${gradeToClass(data?.grade)}`}
              >
                <div className="dimension-label">{label}</div>
                <div className={`dimension-grade ${gradeToClass(data?.grade)}`}>
                  {data?.grade?.toUpperCase() ?? "—"}
                </div>
                {data?.evidence && (
                  <div className="dimension-evidence">&quot;{data.evidence}&quot;</div>
                )}
              </div>
            ))}
          </div>

          {/* Divergence Alert for Sep-18 */}
          {date === "2024-09-18" && (
            <>
              <div className="divider" />
              <div
                style={{
                  border: "1px solid var(--red)",
                  background: "rgba(255,59,48,0.04)",
                  padding: "14px 20px",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: "var(--sp-8)",
                }}
              >
                <span
                  style={{
                    color: "var(--red)",
                    fontWeight: 800,
                    fontSize: 10,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                  }}
                >
                  ⚠ DIVERGENCE DETECTED
                </span>
                <span style={{ fontSize: 12, color: "#888" }}>
                  Labor market assessment contradicts UNRATE data (4.2% → 4.1%).
                  Fed said &quot;moved up&quot;, data shows &quot;moved down&quot;.
                </span>
                <Link href="/divergences" style={{ marginLeft: "auto" }}>
                  <span className="badge badge-red">FULL REPORT →</span>
                </Link>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
