import { NextRequest, NextResponse } from "next/server";
import { getInterviewAgentBaseUrl } from "@/lib/interview-agent";

export async function POST(request: NextRequest) {
  // Pass raw body straight through — do NOT parse/re-serialize FormData.
  // Parsing and re-serializing multipart can corrupt the binary audio data
  // or generate a mismatched boundary that FastAPI rejects.
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
  const timeout = setTimeout(() => controller.abort(), 30_000);

  try {
    const upstream = await fetch(`${baseUrl}/v1/stt`, {
      method: "POST",
      headers: { "Content-Type": contentType },
      body: rawBody,
      cache: "no-store",
      signal: controller.signal,
    });

    if (!upstream.ok) {
      const detail = await upstream.text().catch(() => "");
      return NextResponse.json(
        { error: "stt_failed", upstreamStatus: upstream.status, detail },
        { status: upstream.status }
      );
    }

    const data = (await upstream.json()) as { transcript?: string };
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "stt_unavailable", details: String(error) }, { status: 503 });
  } finally {
    clearTimeout(timeout);
  }
}
