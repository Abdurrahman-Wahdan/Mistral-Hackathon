import { NextRequest, NextResponse } from "next/server";
import { fetchInterviewAgent } from "@/lib/interview-agent";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  try {
    const upstream = await fetchInterviewAgent("/v1/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!upstream.ok) {
      return NextResponse.json({ error: "tts_failed", upstreamStatus: upstream.status }, { status: upstream.status });
    }

    // Stream the response directly — don't buffer with arrayBuffer()
    // This lets the browser start playing audio as the first MP3 chunks arrive
    return new NextResponse(upstream.body, {
      headers: {
        "Content-Type": "audio/mpeg",
        "Cache-Control": "no-store",
        "Transfer-Encoding": "chunked",
      },
    });
  } catch (error) {
    return NextResponse.json({ error: "tts_unavailable", details: String(error) }, { status: 503 });
  }
}
