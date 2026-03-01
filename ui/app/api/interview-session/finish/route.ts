import { NextRequest, NextResponse } from "next/server";
import {
  fetchInterviewAgentWithRetry,
  getInterviewAgentBaseUrl,
  parseJsonSafe,
} from "@/lib/interview-agent";

interface FinishBody {
  sessionId?: unknown;
  jobTitle?: unknown;
  force?: unknown;
}

export async function POST(request: NextRequest) {
  let body: FinishBody = {};
  try {
    body = (await request.json()) as FinishBody;
  } catch {
    body = {};
  }

  const sessionId = typeof body.sessionId === "string" ? body.sessionId.trim() : "";
  const jobTitle = typeof body.jobTitle === "string" ? body.jobTitle.trim() : "";
  const force = typeof body.force === "boolean" ? body.force : true;

  if (!sessionId) {
    return NextResponse.json({ error: "session_id_required" }, { status: 400 });
  }

  try {
    const upstream = await fetchInterviewAgentWithRetry(
      `/v1/interview/sessions/${encodeURIComponent(sessionId)}/finish`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ force, job_title: jobTitle || undefined }),
      }
    );

    const payload = await parseJsonSafe(upstream);
    if (!upstream.ok) {
      return NextResponse.json(
        { error: "finish_failed", upstreamStatus: upstream.status, details: payload },
        { status: upstream.status }
      );
    }

    return NextResponse.json(payload, {
      headers: { "Cache-Control": "no-store" },
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
