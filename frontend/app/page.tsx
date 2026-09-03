import Link from "next/link";
import QnA from "@/components/QnA";
import { getMeetings, getMeetingDetail, type Meeting, type MeetingDetail } from "@/lib/api";

function gradeToClass(grade: string | undefined): string {
  if (!grade) return "grey";
  const g = grade.toLowerCase();
  if (g === "improving") return "green";
  if (g === "deteriorating") return "red";
  if (g === "stable") return "amber";
  if (g === "dovish") return "green";
  if (g === "hawkish") return "red";
  return "blue";
}

async function getEnrichedMeetings() {
  const meetings = await getMeetings();
  const details = await Promise.all(
    meetings.map((m) => getMeetingDetail(m.date).catch(() => null))
  );
  return meetings.map((m, i) => ({ meeting: m, detail: details[i] }));
}

export default async function DashboardPage() {
  let enriched: { meeting: Meeting; detail: MeetingDetail | null }[] = [];
  let error = false;

  try {
    enriched = await getEnrichedMeetings();
  } catch {
    error = true;
  }

  const latest = enriched[0];
  const latestStance = latest?.detail?.assessment?.overall_stance;
  const totalMeetings = enriched.length;
  const latestShift = latest?.detail?.change_detection?.hawkish_or_dovish;

  return (
    <>
      <div className="page-header">
        <div className="page-breadcrumb">FOMC Intelligence System</div>
        <h1 className="page-title">Policy Dashboard</h1>
        <div className="page-meta">
          <span className="badge badge-grey">MVP v1.0</span>
          <span style={{ fontSize: 11, color: "#444" }}>
            Data coverage: 2024 · gpt-4o-mini extraction
          </span>
        </div>
      </div>

      {error ? (
        <div className="empty">
          <div className="empty-icon">⚠</div>
          <div className="empty-title">API Unreachable</div>
          <div className="empty-sub">
            Start the backend:{" "}
            <code style={{ color: "#666" }}>
              uv run uvicorn app.api.main:app --reload
            </code>
          </div>
        </div>
      ) : (
        <>
          {/* Stat Strip */}
          <div className="stat-grid">
            <div className="stat-cell">
              <div className="stat-label">Meetings Analyzed</div>
              <div className="stat-value">{totalMeetings}</div>
              <div className="stat-delta">2024 FOMC calendar</div>
            </div>
            <div className="stat-cell">
              <div className="stat-label">Latest Stance</div>
              <div className={`stat-value ${gradeToClass(latestStance?.grade)}`}>
                {latestStance?.grade?.toUpperCase() ?? "—"}
              </div>
              <div className="stat-delta">{latest?.meeting.date ?? "—"}</div>
            </div>
            <div className="stat-cell">
              <div className="stat-label">Policy Shift Direction</div>
              <div className={`stat-value ${gradeToClass(latestShift)}`}>
                {latestShift?.toUpperCase() ?? "—"}
              </div>
              <div className="stat-delta">vs previous meeting</div>
            </div>
            <div className="stat-cell">
              <div className="stat-label">Divergences Detected</div>
              <div className="stat-value red">1</div>
              <div className="stat-delta">Labor market · Sep 2024</div>
            </div>
          </div>

          {/* Meetings Table */}
          <div className="section-header">
            <div className="section-title">
              <span>FOMC Meetings</span> — Click any row for full intelligence report
            </div>
          </div>

          <div className="card" style={{ padding: 0 }}>
            <table className="meeting-table">
              <thead>
                <tr>
                  <th>Meeting Date</th>
                  <th>Overall Stance</th>
                  <th>Inflation</th>
                  <th>Labor Market</th>
                  <th>Economic Growth</th>
                  <th>Forward Guidance</th>
                  <th>Fin. Conditions</th>
                  <th>Policy Shift</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {enriched.map(({ meeting, detail }) => {
                  const a = detail?.assessment;
                  const shift = detail?.change_detection?.hawkish_or_dovish;

                  return (
                    <tr key={meeting.id}>
                      <td>
                        <Link
                          href={`/meetings/${meeting.date}`}
                          style={{ display: "block" }}
                        >
                          <span className="date-cell">{meeting.date}</span>
                        </Link>
                      </td>
                      <td>
                        {a?.overall_stance ? (
                          <span
                            className={`badge badge-${gradeToClass(a.overall_stance.grade)}`}
                          >
                            {a.overall_stance.grade.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        {a?.inflation ? (
                          <span
                            className={`badge badge-${gradeToClass(a.inflation.grade)}`}
                          >
                            {a.inflation.grade.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        {a?.labor_market ? (
                          <span
                            className={`badge badge-${gradeToClass(a.labor_market.grade)}`}
                          >
                            {a.labor_market.grade.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        {a?.economic_growth ? (
                          <span
                            className={`badge badge-${gradeToClass(a.economic_growth.grade)}`}
                          >
                            {a.economic_growth.grade.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        {a?.forward_guidance ? (
                          <span
                            className={`badge badge-${gradeToClass(a.forward_guidance.grade)}`}
                          >
                            {a.forward_guidance.grade.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        {a?.financial_conditions ? (
                          <span
                            className={`badge badge-${gradeToClass(a.financial_conditions.grade)}`}
                          >
                            {a.financial_conditions.grade.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        {shift ? (
                          <span
                            className={`badge badge-${gradeToClass(shift)}`}
                          >
                            {shift.toUpperCase()}
                          </span>
                        ) : (
                          <span className="mono">—</span>
                        )}
                      </td>
                      <td>
                        <Link
                          href={`/meetings/${meeting.date}`}
                          className="badge badge-grey"
                        >
                          VIEW →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Divergence Alert Banner */}
          <div className="divider" />
          <div
            style={{
              border: "1px solid var(--red)",
              background: "rgba(255,59,48,0.04)",
              padding: "14px 20px",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <span
              style={{
                color: "var(--red)",
                fontWeight: 800,
                fontSize: 10,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                whiteSpace: "nowrap",
              }}
            >
              ⚠ DIVERGENCE ALERT
            </span>
            <span style={{ fontSize: 12, color: "#888" }}>
              Sep 2024 — Fed labeled labor market as DETERIORATING while UNRATE
              data showed 4.2% → 4.1% (improving). Divergence severity:{" "}
              <strong style={{ color: "var(--red)" }}>HIGH</strong>.
            </span>
            <Link href="/divergences" style={{ marginLeft: "auto" }}>
              <span className="badge badge-red">INSPECT →</span>
            </Link>
          </div>
          
          <QnA />
        </>
      )}
    </>
  );
}
