import { NextRequest, NextResponse } from "next/server";
import {
  fetchInterviewAgentWithRetry,
  getInterviewAgentBaseUrl,
  parseJsonSafe,
} from "@/lib/interview-agent";

export async function POST(request: NextRequest) {
  let rawBody: Record<string, unknown> = {};
  try {
    rawBody = (await request.json()) as Record<string, unknown>;
  } catch {
    rawBody = {};
  }

  const sessionId =
    typeof rawBody.sessionId === "string" && rawBody.sessionId.trim()
      ? rawBody.sessionId.trim()
      : undefined;
  const jobTitle =
    typeof rawBody.jobTitle === "string" && rawBody.jobTitle.trim()
      ? rawBody.jobTitle.trim()
      : undefined;

  const payload: Record<string, unknown> = {
    session_id: sessionId,
    job_title: jobTitle,
  };

  try {
    const upstream = await fetchInterviewAgentWithRetry("/v1/interview/sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const body = await parseJsonSafe(upstream);
    if (!upstream.ok) {
      return NextResponse.json(
        { error: "start_session_failed", upstreamStatus: upstream.status, details: body },
        { status: upstream.status }
      );
    }

    return NextResponse.json(body, {
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
