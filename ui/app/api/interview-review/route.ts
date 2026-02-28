import { NextRequest, NextResponse } from "next/server";

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

const toSlug = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

const buildFallbackPayload = (jobTitle: string): InterviewReviewPayload => {
  const now = new Date();
  const timestamp = now.toISOString();
  const slug = toSlug(jobTitle || "interview");

  const summary = `You communicated clearly with strong role alignment for ${jobTitle}. Keep sharpening impact-focused examples and close answers with measurable outcomes.`;

  const analysisHighlights = [
    "Strong structure in most responses (context -> action -> result).",
    "Technical depth is good, but answers can be more concise under time pressure.",
    "Confidence and pacing improved as the interview progressed.",
    "Add one concrete project metric in each major example.",
  ];

  const content = [
    `Interview Review Report - ${jobTitle}`,
    `Generated At: ${timestamp}`,
    "",
    "Summary",
    summary,
    "",
    "Highlights",
    ...analysisHighlights.map((item, index) => `${index + 1}. ${item}`),
    "",
    "Recommendations",
    "1. Use a tighter STAR format with a quantified result in every answer.",
    "2. Prepare one strong end-of-interview question for hiring managers.",
    "3. Rehearse technical explanations in 60-90 second versions.",
  ].join("\n");

  return {
    summary,
    analysisHighlights,
    report: {
      id: `report-${Date.now()}`,
      fileName: `${slug || "interview"}-review-report.txt`,
      createdAt: timestamp,
      mimeType: "text/plain",
      content,
    },
  };
};

export async function POST(request: NextRequest) {
  let jobTitle = "the selected role";

  try {
    const body = (await request.json()) as { jobTitle?: unknown };
    if (typeof body.jobTitle === "string" && body.jobTitle.trim()) {
      jobTitle = body.jobTitle.trim();
    }
  } catch {
    // Fall back to default title if body is missing or invalid.
  }

  const upstreamUrl = process.env.INTERVIEW_REVIEW_API_URL;

  if (upstreamUrl) {
    try {
      const upstreamResponse = await fetch(upstreamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ jobTitle }),
        cache: "no-store",
      });

      if (upstreamResponse.ok) {
        const payload = (await upstreamResponse.json()) as InterviewReviewPayload;
        return NextResponse.json(payload, {
          headers: {
            "Cache-Control": "no-store",
          },
        });
      }
    } catch {
      // Fall through to fallback payload.
    }
  }

  return NextResponse.json(buildFallbackPayload(jobTitle), {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
