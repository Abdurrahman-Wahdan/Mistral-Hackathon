import { NextRequest, NextResponse } from "next/server";
import {
  fetchInterviewAgentWithRetry,
  getInterviewAgentBaseUrl,
  parseJsonSafe,
} from "@/lib/interview-agent";

interface TurnBody {
  sessionId?: unknown;
  candidateMessage?: unknown;
}

export async function POST(request: NextRequest) {
  let body: TurnBody = {};
  try {
    body = (await request.json()) as TurnBody;
  } catch {
    body = {};
  }

  const sessionId = typeof body.sessionId === "string" ? body.sessionId.trim() : "";
  const candidateMessage = typeof body.candidateMessage === "string" ? body.candidateMessage.trim() : "";

  if (!sessionId) {
    return NextResponse.json({ error: "session_id_required" }, { status: 400 });
  }
  if (!candidateMessage) {
    return NextResponse.json({ error: "candidate_message_required" }, { status: 400 });
  }

  try {
    const upstream = await fetchInterviewAgentWithRetry(
      `/v1/interview/sessions/${encodeURIComponent(sessionId)}/turn`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ candidate_message: candidateMessage }),
      }
    );

    const payload = await parseJsonSafe(upstream);
    if (!upstream.ok) {
      return NextResponse.json(
        { error: "turn_failed", upstreamStatus: upstream.status, details: payload },
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
