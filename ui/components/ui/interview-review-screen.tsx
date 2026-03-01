"use client";

import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import type { ComponentPropsWithoutRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { LiquidMetal, liquidMetalPresets } from "@paper-design/shaders-react";
import ReactMarkdown from "react-markdown";
import { LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer } from "recharts";
import type { InterviewReviewPayload } from "@/lib/interview-review-types";

interface InterviewReviewScreenProps {
  jobTitle: string;
  sessionId: string | null;
  initialReview?: InterviewReviewPayload | null;
  onClose: () => void;
}

const MIN_LOADING_MS = 2600;
type MarkdownCodeProps = ComponentPropsWithoutRef<"code"> & { inline?: boolean };

function normalizeMarkdown(raw: string): string {
  const source = (raw ?? "").trim();
  if (!source) return "";

  // If the model wrapped the entire report in a fenced block, unwrap it.
  const fencedMatch = source.match(/^```[a-zA-Z0-9_-]*\n([\s\S]*?)\n```$/);
  let normalized = fencedMatch ? fencedMatch[1] : source;

  // Handle occasionally escaped payloads.
  if (!normalized.includes("\n") && normalized.includes("\\n")) {
    normalized = normalized.replace(/\\n/g, "\n");
  }
  normalized = normalized.replace(/\\"/g, '"');

  return normalized.trim();
}

export default function InterviewReviewScreen({
  jobTitle,
  sessionId,
  initialReview = null,
  onClose,
}: InterviewReviewScreenProps) {
  const [stage, setStage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [review, setReview] = useState<InterviewReviewPayload | null>(initialReview);
  const [error, setError] = useState<string | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const pdfRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t1 = setTimeout(() => setStage(1), 450);
    const t2 = setTimeout(() => setStage(2), 1200);
    const t3 = setTimeout(() => setStage(3), 1900);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  const loadReview = useCallback(async (signal?: AbortSignal) => {
    if (initialReview) {
      setReview(initialReview);
      setError(null);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [response] = await Promise.all([
        fetch("/api/interview-review", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ jobTitle, sessionId }),
          signal,
        }),
        new Promise((resolve) => setTimeout(resolve, MIN_LOADING_MS)),
      ]);

      if (signal?.aborted) return;

      if (!response.ok) {
        throw new Error("Failed to load interview performance review");
      }

      const payload = (await response.json()) as InterviewReviewPayload;
      setReview(payload);
    } catch {
      if (signal?.aborted) return;
      setError("Could not load your interview performance report. Please try again.");
    } finally {
      if (signal?.aborted) return;
      setIsLoading(false);
    }
  }, [initialReview, jobTitle, sessionId]);

  useEffect(() => {
    const controller = new AbortController();
    void loadReview(controller.signal);
    return () => controller.abort();
  }, [loadReview]);

  const reportDate = useMemo(() => {
    if (!review) return "";
    const date = new Date(review.report.createdAt);
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }, [review]);

  const parsedReportContent = useMemo(() => {
    return normalizeMarkdown(review?.report.content ?? "");
  }, [review?.report.content]);
  const parsedSummary = useMemo(() => normalizeMarkdown(review?.summary ?? ""), [review?.summary]);
  const hasStrengths = (review?.strengths?.length ?? 0) > 0;
  const hasWeaknesses = (review?.weaknesses?.length ?? 0) > 0;
  const showTwoSignalCards = hasStrengths && hasWeaknesses;

  const scoreCards = useMemo(() => {
    if (!review) return [];
    const signalStrength = Math.min(92, 72 + review.analysisHighlights.length * 4);
    const clarityScore = Math.min(95, 70 + review.analysisHighlights.length * 5);
    const readinessScore = Math.min(90, 68 + review.analysisHighlights.length * 4);

    return [
      { label: "Signal", value: signalStrength },
      { label: "Clarity", value: clarityScore },
      { label: "Readiness", value: readinessScore },
    ];
  }, [review]);

  const scoreLabel = useMemo(() => {
    if (!review) return "Pending";
    if (review.overallScore >= 85) return "Excellent";
    if (review.overallScore >= 70) return "Strong";
    if (review.overallScore >= 55) return "Mixed";
    return "Needs Work";
  }, [review]);

  const phaseTrend = useMemo(() => {
    if (!review || !review.phases || review.phases.length < 2) return "";
    const first = review.phases[0]?.score ?? 0;
    const last = review.phases[review.phases.length - 1]?.score ?? 0;
    const delta = last - first;
    if (delta > 8) return `Strong recovery: +${delta} points from opening to closing.`;
    if (delta < -8) return `Performance dipped by ${Math.abs(delta)} points from opening to closing.`;
    return "Performance stayed relatively stable across interview phases.";
  }, [review]);

  const downloadPdf = async () => {
    if (!review || !pdfRef.current) return;
    setIsGeneratingPdf(true);

    // Dynamically import html2pdf to avoid SSR issues
    try {
      const html2pdf = (await import("html2pdf.js")).default;
      const element = pdfRef.current;
      const opt = {
        margin: 10,
        filename: `${review.report.fileName.replace('.md', '')}.pdf`,
        image: { type: 'jpeg' as const, quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const }
      };

      await html2pdf().set(opt).from(element).save();
    } catch (e) {
      console.error("Failed to generate PDF", e);
      setError("Failed to generate PDF from report preview. Please retry.");
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const heroBackground = (
    <div className="fixed inset-0 z-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.14),transparent_45%),radial-gradient(circle_at_80%_70%,rgba(255,255,255,0.08),transparent_42%),#000]">
      <LiquidMetal
        {...liquidMetalPresets[1]}
        colorBack="#000000"
        colorTint="#4a4a4a"
        shape="circle"
        scale={2.5}
        softness={0.7}
        contour={0.6}
        distortion={0.4}
        shiftRed={-0.15}
        shiftBlue={0.25}
        speed={0.7}
        style={{ position: "absolute", inset: 0, width: "100vw", height: "100vh" }}
      />
    </div>
  );

  if (isLoading) {
    return (
      <section className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden px-6">
        {heroBackground}
        <div className="pointer-events-none absolute inset-0 z-0 bg-black/55" />

        <div className="relative z-10 w-full max-w-2xl rounded-3xl border border-white/15 bg-black/70 p-8 sm:p-10 backdrop-blur-2xl">
          <p className="mb-4 text-xs uppercase tracking-[0.22em] text-foreground/40">Post Interview</p>
          <h2 className="text-3xl sm:text-4xl font-semibold text-foreground mb-4">Generating your final interview report</h2>

          <AnimatePresence>
            {stage >= 1 && (
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-foreground/55"
              >
                Compiling role-specific analysis for <span className="text-foreground/80">{jobTitle}</span>
              </motion.p>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {stage >= 2 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-8"
              >
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                  <motion.div
                    className="h-full bg-white/80"
                    initial={{ width: "15%" }}
                    animate={{ width: ["15%", "45%", "70%", "92%"] }}
                    transition={{ duration: 2.2, ease: "easeInOut" }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {stage >= 3 && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-5 text-sm text-foreground/40"
              >
                Finalizing strengths, weaknesses, and coaching recommendations...
              </motion.p>
            )}
          </AnimatePresence>
        </div>
      </section>
    );
  }

  if (error || !review) {
    return (
      <section className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden px-6">
        {heroBackground}
        <div className="pointer-events-none absolute inset-0 z-0 bg-black/55" />

        <div className="relative z-10 w-full max-w-xl rounded-2xl border border-white/15 bg-black/70 backdrop-blur-xl p-8 text-center">
          <h2 className="text-2xl font-bold text-foreground mb-3">Review unavailable</h2>
          <p className="text-foreground/60 mb-8">{error ?? "No report was returned by the backend."}</p>
          <div className="flex items-center justify-center gap-4">
            <Button
              variant="outline"
              className="border-white/20 bg-transparent text-foreground hover:bg-white/10"
              onClick={onClose}
            >
              Back to roles
            </Button>
            <Button className="bg-white text-black hover:bg-white/90" onClick={() => void loadReview()}>
              Retry
            </Button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="fixed inset-0 z-50 overflow-y-auto overflow-x-hidden bg-black">
      {heroBackground}
      <div className="pointer-events-none fixed inset-0 z-0 bg-black/55" />

      <div className="relative z-10 min-h-full px-6 py-10 sm:py-14 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="w-full max-w-6xl overflow-hidden rounded-[30px] border border-white/15 bg-black/72 shadow-[0_40px_120px_rgba(0,0,0,0.7)] backdrop-blur-2xl"
        >
          <div className="border-b border-white/10 px-6 py-5 sm:px-8 sm:py-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-foreground/40 mb-2">Interview Intelligence</p>
                <h2 className="text-2xl sm:text-3xl font-semibold text-foreground">Your interview review is ready</h2>
                <p className="mt-2 text-sm text-foreground/50">Role: <span className="text-foreground/80">{jobTitle}</span></p>
              </div>
              <div className="rounded-full border border-white/20 bg-black/60 px-4 py-2 text-sm text-foreground/75">
                Final report generated
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 p-6 sm:p-8">
            <div className="lg:col-span-7 space-y-5">
              <div className="flex flex-col sm:flex-row gap-5">
                <div className="flex-1 rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6 flex flex-col justify-center items-center">
                  <p className="text-xs uppercase tracking-[0.16em] text-foreground/40 mb-3">Overall Performance</p>
                  <div className="relative flex items-center justify-center w-32 h-32 rounded-full border-[6px] border-white/10">
                    <svg className="absolute inset-0 w-full h-full -rotate-90">
                      <circle
                        cx="50%"
                        cy="50%"
                        r="46%"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="12"
                        className="text-white"
                        strokeDasharray="289"
                        strokeDashoffset={289 - (289 * (review.overallScore || 0)) / 100}
                        strokeLinecap="round"
                      />
                    </svg>
                    <span className="text-4xl font-bold">{review.overallScore || 0}%</span>
                  </div>
                  <div className="mt-3 rounded-full border border-white/20 px-3 py-1 text-xs uppercase tracking-[0.12em] text-foreground/80">
                    {scoreLabel}
                  </div>
                </div>

                <div className="flex-[2] rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                  <p className="mb-2 text-xs uppercase tracking-[0.16em] text-foreground/40">Summary</p>
                  <div className="text-foreground/80 leading-relaxed text-sm sm:text-base">
                    <ReactMarkdown
                      components={{
                        p: ({ ...props }) => <p className="mb-3 last:mb-0" {...props} />,
                        strong: ({ ...props }) => <strong className="font-semibold text-foreground" {...props} />,
                        em: ({ ...props }) => <em className="italic text-foreground/90" {...props} />,
                      }}
                    >
                      {parsedSummary}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>

              {review.phases && review.phases.length > 0 && (
                <div className="rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                  <p className="mb-4 text-xs uppercase tracking-[0.16em] text-foreground/40">Performance Timeline</p>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={review.phases}>
                        <XAxis dataKey="name" stroke="#ffffff60" fontSize={11} tickMargin={8} />
                        <YAxis stroke="#ffffff60" fontSize={11} domain={[0, 100]} hide />
                        <RechartsTooltip
                          contentStyle={{ backgroundColor: '#000000f0', border: '1px solid #ffffff20', borderRadius: '8px' }}
                          itemStyle={{ color: '#ffffff' }}
                        />
                        <Line type="monotone" dataKey="score" stroke="#ffffff" strokeWidth={3} dot={{ r: 4, fill: '#fff' }} activeDot={{ r: 6 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  {phaseTrend ? <p className="mt-3 text-xs text-foreground/60">{phaseTrend}</p> : null}
                </div>
              )}

              {review.analysisHighlights && review.analysisHighlights.length > 0 && (
                <div className="rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                  <p className="mb-4 text-xs uppercase tracking-[0.16em] text-foreground/40">Session Highlights</p>
                  <ul className="space-y-2">
                    {review.analysisHighlights.slice(0, 5).map((item, idx) => (
                      <li key={idx} className="text-sm text-foreground/80 leading-relaxed">
                        <ReactMarkdown
                          components={{
                            p: ({ ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                            strong: ({ ...props }) => <strong className="font-semibold text-foreground" {...props} />,
                            em: ({ ...props }) => <em className="italic text-foreground/90" {...props} />,
                            ul: ({ ...props }) => <ul className="list-disc pl-5 space-y-1" {...props} />,
                            li: ({ ...props }) => <li className="mb-1" {...props} />,
                          }}
                        >
                          {normalizeMarkdown(item)}
                        </ReactMarkdown>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className={`grid grid-cols-1 ${showTwoSignalCards ? "sm:grid-cols-2" : "sm:grid-cols-1"} gap-5`}>
                {review.strengths && review.strengths.length > 0 && (
                  <div className="rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                    <p className="mb-4 text-xs uppercase tracking-[0.16em] text-foreground/40">Key Strengths</p>
                    <ul className="space-y-3">
                      {review.strengths.map((str, idx) => (
                        <li key={idx} className="flex gap-3 text-sm text-foreground/80">
                          <span className="text-green-400 mt-0.5">✓</span> <span>{str}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {review.weaknesses && review.weaknesses.length > 0 && (
                  <div className="rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                    <p className="mb-4 text-xs uppercase tracking-[0.16em] text-foreground/40">Areas for Improvement</p>
                    <ul className="space-y-3">
                      {review.weaknesses.map((weak, idx) => (
                        <li key={idx} className="flex gap-3 text-sm text-foreground/80">
                          <span className="text-red-400 mt-0.5">✕</span> <span>{weak}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            <div className="lg:col-span-5 space-y-5">
              <div className="flex flex-col gap-3">
                <p className="text-xs uppercase tracking-[0.16em] text-foreground/40 mb-1">Detailed Metrics</p>
                {review.detailedMetrics && review.detailedMetrics.length > 0 ? (
                  review.detailedMetrics.map((metric) => (
                    <div key={metric.label} className="rounded-xl border border-white/12 bg-black/55 p-4 flex flex-col justify-between">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-foreground">{metric.label}</span>
                        <span className="text-sm font-bold text-foreground">{metric.score}/100</span>
                      </div>
                      <div className="w-full h-1.5 bg-white/10 rounded-full mb-3 overflow-hidden">
                        <div className="h-full bg-white/80 rounded-full" style={{ width: `${metric.score}%` }} />
                      </div>
                      <p className="text-xs text-foreground/60">{metric.feedback}</p>
                    </div>
                  ))
                ) : (
                  scoreCards.map((score) => (
                    <div key={score.label} className="rounded-xl border border-white/12 bg-black/55 p-3 text-center">
                      <p className="text-[11px] uppercase tracking-[0.14em] text-foreground/45">{score.label}</p>
                      <p className="mt-2 text-xl font-semibold text-foreground">{score.value}</p>
                    </div>
                  ))
                )}
              </div>

              <button
                type="button"
                className="w-full text-left rounded-2xl border border-white/15 bg-black/55 hover:bg-black/65 transition-all p-5"
                onClick={() => setIsReportModalOpen(true)}
              >
                <p className="text-xs uppercase tracking-[0.16em] text-foreground/40 mb-2">Report file</p>
                <p className="text-lg font-medium text-foreground break-all">{review.report.fileName}</p>
                <p className="mt-2 text-sm text-foreground/45">Generated {reportDate}</p>
                <div className="mt-4 inline-flex items-center rounded-full border border-white/20 px-3 py-1 text-xs text-foreground/70">
                  Open, review, and download
                </div>
              </button>

              <div className="rounded-2xl border border-white/12 bg-black/55 p-5">
                <p className="text-xs uppercase tracking-[0.16em] text-foreground/40 mb-2">Recommended next step</p>
                <p className="text-sm text-foreground/65">
                  Apply the recommendations, then run a new session to measure improvement against this baseline.
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-white/10 px-6 py-4 sm:px-8 flex justify-end">
            <Button
              size="lg"
              variant="outline"
              className="border-white/20 text-foreground hover:bg-white/10 bg-transparent"
              onClick={onClose}
            >
              Back to Roles
            </Button>
          </div>
        </motion.div>
      </div>

      <AnimatePresence>
        {isReportModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-md flex items-center justify-center px-4"
            onClick={() => setIsReportModalOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.97, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.97, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="w-full max-w-4xl overflow-hidden rounded-2xl border border-white/15 bg-[#0a0a0a] shadow-[0_30px_90px_rgba(0,0,0,0.7)]"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="border-b border-white/10 px-5 py-4 sm:px-6 sm:py-5 flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-foreground/45 mb-1">Report Preview</p>
                  <p className="text-sm sm:text-base text-foreground/90 break-all">{review.report.fileName}</p>
                </div>
                <button
                  type="button"
                  className="text-foreground/55 hover:text-foreground transition-colors text-2xl leading-none"
                  onClick={() => setIsReportModalOpen(false)}
                  aria-label="Close report preview"
                >
                  &times;
                </button>
              </div>

              <div className="max-h-[58vh] overflow-y-auto px-5 py-4 sm:px-6 sm:py-5 bg-white text-black" ref={pdfRef}>
                <div className="max-w-none text-[15px] leading-7">
                  <ReactMarkdown
                    components={{
                      h1: ({ ...props }) => <h1 className="mt-2 mb-5 text-3xl font-semibold tracking-tight text-black" {...props} />,
                      h2: ({ ...props }) => <h2 className="mt-8 mb-4 text-2xl font-semibold text-black" {...props} />,
                      h3: ({ ...props }) => <h3 className="mt-6 mb-3 text-xl font-semibold text-black" {...props} />,
                      p: ({ ...props }) => <p className="mb-4 text-black/90" {...props} />,
                      ul: ({ ...props }) => <ul className="mb-4 list-disc pl-6 text-black/90" {...props} />,
                      ol: ({ ...props }) => <ol className="mb-4 list-decimal pl-6 text-black/90" {...props} />,
                      li: ({ ...props }) => <li className="mb-1" {...props} />,
                      hr: ({ ...props }) => <hr className="my-6 border-black/15" {...props} />,
                      strong: ({ ...props }) => <strong className="font-semibold text-black" {...props} />,
                      blockquote: ({ ...props }) => (
                        <blockquote className="my-4 border-l-4 border-black/20 bg-black/[0.03] px-4 py-2 italic text-black/80" {...props} />
                      ),
                      code: ({ inline, className, children, ...props }: MarkdownCodeProps) =>
                        inline ? (
                          <code className="rounded bg-black/10 px-1.5 py-0.5 font-mono text-[0.92em]" {...props}>
                            {children}
                          </code>
                        ) : (
                          <code className={`block overflow-x-auto rounded-lg bg-black text-white p-4 font-mono text-sm ${className ?? ""}`} {...props}>
                            {children}
                          </code>
                        ),
                    }}
                  >
                    {parsedReportContent}
                  </ReactMarkdown>
                </div>
              </div>

              <div className="border-t border-white/10 bg-white/[0.02] px-5 py-4 sm:px-6 flex items-center justify-end gap-3">
                <Button
                  variant="outline"
                  className="border-white/20 bg-transparent text-foreground hover:bg-white/10"
                  onClick={() => setIsReportModalOpen(false)}
                >
                  Close
                </Button>
                <Button className="bg-white text-black hover:bg-white/90" onClick={downloadPdf} disabled={isGeneratingPdf}>
                  {isGeneratingPdf ? "Generating PDF..." : "Download PDF"}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
