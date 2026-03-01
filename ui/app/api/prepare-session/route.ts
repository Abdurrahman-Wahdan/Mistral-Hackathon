import { NextRequest, NextResponse } from "next/server";
import { getInterviewAgentBaseUrl } from "@/lib/interview-agent";

export async function POST(request: NextRequest) {
  // Pass raw multipart body straight through — same pattern as /api/stt
  const contentType = request.headers.get("content-type") ?? "";
  if (!contentType.startsWith("multipart/form-data")) {
    return NextResponse.json({ error: "expected_multipart" }, { status: 400 });
  }

  let rawBody: ArrayBuffer;
  try {
    rawBody = await request.arrayBuffer();
  } catch {
    return NextResponse.json({ error: "failed_to_read_body" }, { status: 400 });
  }

  const baseUrl = getInterviewAgentBaseUrl();
  const controller = new AbortController();
  // Question generation can be long when multiple agent branches run in parallel.
  const timeout = setTimeout(() => controller.abort(), 300_000);

  try {
    const upstream = await fetch(`${baseUrl}/v1/prepare-session`, {
      method: "POST",
      headers: { "Content-Type": contentType },
      body: rawBody,
      cache: "no-store",
      signal: controller.signal,
    });

    if (!upstream.ok) {
      const detail = await upstream.text().catch(() => "");
      return NextResponse.json(
        { error: "prepare_session_failed", upstreamStatus: upstream.status, detail },
        { status: upstream.status }
      );
    }

    const data = (await upstream.json()) as { session_id?: string };
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "prepare_session_unavailable", details: String(error) },
      { status: 503 }
    );
  } finally {
    clearTimeout(timeout);
  }
}
