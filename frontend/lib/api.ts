const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Meeting {
  id: string;
  date: string;
  rate_decision: string | null;
}

export interface AssessmentDimension {
  grade: string;
  evidence: string;
}

export interface MeetingDetail {
  meeting_date: string;
  assessment: {
    inflation?: AssessmentDimension;
    labor_market?: AssessmentDimension;
    economic_growth?: AssessmentDimension;
    financial_conditions?: AssessmentDimension;
    forward_guidance?: AssessmentDimension;
    overall_stance?: AssessmentDimension;
  } | null;
  change_detection?: {
    summary_of_changes?: string;
    hawkish_or_dovish?: string;
    key_takeaway?: string;
  } | null;
}

export async function getMeetings(): Promise<Meeting[]> {
  const res = await fetch(`${API_BASE}/api/v1/meetings`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch meetings");
  return res.json();
}

export async function getMeetingDetail(date: string): Promise<MeetingDetail> {
  const res = await fetch(`${API_BASE}/api/v1/meetings/${date}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch meeting detail");
  return res.json();
}
