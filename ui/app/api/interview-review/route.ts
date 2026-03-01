import { NextRequest, NextResponse } from "next/server";
import { fetchInterviewAgent, getInterviewAgentBaseUrl, parseJsonSafe } from "@/lib/interview-agent";

interface InterviewReviewPayload {
  summary: string;
  analysisHighlights: string[];
  report: {
    id: string;
    fileName: string;
    createdAt: string;
    mimeType: string;
    content: string;
  };
}

function isValidReviewPayload(payload: unknown): payload is InterviewReviewPayload {
  if (!payload || typeof payload !== "object") return false;
  const parsed = payload as Partial<InterviewReviewPayload>;
  if (typeof parsed.summary !== "string") return false;
  if (!Array.isArray(parsed.analysisHighlights)) return false;
  if (!parsed.report || typeof parsed.report !== "object") return false;
  const report = parsed.report as Partial<InterviewReviewPayload["report"]>;
  return (
    typeof report.id === "string" &&
    typeof report.fileName === "string" &&
    typeof report.createdAt === "string" &&
    typeof report.mimeType === "string" &&
    typeof report.content === "string"
  );
}

export async function POST(request: NextRequest) {
  let jobTitle = "";
  let sessionId = "";

  try {
    const body = (await request.json()) as { jobTitle?: unknown; sessionId?: unknown };
    if (typeof body.jobTitle === "string" && body.jobTitle.trim()) {
      jobTitle = body.jobTitle.trim();
    }
    if (typeof body.sessionId === "string" && body.sessionId.trim()) {
      sessionId = body.sessionId.trim();
    }
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  if (!sessionId) {
    return NextResponse.json({ error: "session_id_required" }, { status: 400 });
  }

  try {
    const upstream = await fetchInterviewAgent(
      `/v1/interview/sessions/${encodeURIComponent(sessionId)}/report?job_title=${encodeURIComponent(jobTitle)}`
    );

    const payload = await parseJsonSafe(upstream);
    if (!upstream.ok) {
      return NextResponse.json(
        {
          error: "review_failed",
          upstreamStatus: upstream.status,
          details: payload,
        },
        { status: upstream.status }
      );
    }

    if (!isValidReviewPayload(payload)) {
      return NextResponse.json(
        { error: "invalid_review_payload", details: payload },
        { status: 502 }
      );
    }

    return NextResponse.json(payload, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "interview_agent_unavailable",
        baseUrl: getInterviewAgentBaseUrl(),
        details: String(error),
      },
      { status: 503 }
    );
  }
}
