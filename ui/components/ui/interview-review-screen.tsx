"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { LiquidMetal, liquidMetalPresets } from "@paper-design/shaders-react";

interface InterviewReportFile {
  id: string;
  fileName: string;
  createdAt: string;
  mimeType: string;
  content: string;
}

interface InterviewReviewPayload {
  summary: string;
  analysisHighlights: string[];
  report: InterviewReportFile;
}

interface InterviewReviewScreenProps {
  jobTitle: string;
  sessionId: string | null;
  onClose: () => void;
}

const MIN_LOADING_MS = 2600;

export default function InterviewReviewScreen({ jobTitle, sessionId, onClose }: InterviewReviewScreenProps) {
  const [stage, setStage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [review, setReview] = useState<InterviewReviewPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);

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
  }, [jobTitle, sessionId]);

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

  const downloadReport = () => {
    if (!review) return;

    const blob = new Blob([review.report.content], { type: review.report.mimeType || "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = review.report.fileName;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const heroBackground = (
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
      style={{ position: "absolute", inset: 0, zIndex: -10 }}
    />
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
    <section className="fixed inset-0 z-50 overflow-y-auto overflow-x-hidden">
      {heroBackground}
      <div className="pointer-events-none absolute inset-0 z-0 bg-black/55" />

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
              <div className="rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                <p className="mb-2 text-xs uppercase tracking-[0.16em] text-foreground/40">Summary</p>
                <p className="text-foreground/80 leading-relaxed text-base sm:text-lg">{review.summary}</p>
              </div>

              <div className="rounded-2xl border border-white/12 bg-black/55 p-5 sm:p-6">
                <p className="mb-4 text-xs uppercase tracking-[0.16em] text-foreground/40">Key interview insights</p>
                <div className="space-y-3">
                  {review.analysisHighlights.map((highlight) => (
                    <div
                      key={highlight}
                      className="rounded-xl border border-white/10 bg-black/45 px-4 py-3 text-foreground/80"
                    >
                      {highlight}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="lg:col-span-5 space-y-5">
              <div className="grid grid-cols-3 gap-3">
                {scoreCards.map((score) => (
                  <div key={score.label} className="rounded-xl border border-white/12 bg-black/55 p-3 text-center">
                    <p className="text-[11px] uppercase tracking-[0.14em] text-foreground/45">{score.label}</p>
                    <p className="mt-2 text-xl font-semibold text-foreground">{score.value}</p>
                  </div>
                ))}
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

              <div className="max-h-[58vh] overflow-y-auto px-5 py-4 sm:px-6 sm:py-5">
                <pre className="rounded-xl border border-white/10 bg-white/[0.02] p-4 text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap font-mono">{review.report.content}</pre>
              </div>

              <div className="border-t border-white/10 bg-white/[0.02] px-5 py-4 sm:px-6 flex items-center justify-end gap-3">
                <Button
                  variant="outline"
                  className="border-white/20 bg-transparent text-foreground hover:bg-white/10"
                  onClick={() => setIsReportModalOpen(false)}
                >
                  Close
                </Button>
                <Button className="bg-white text-black hover:bg-white/90" onClick={downloadReport}>
                  Download Report
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
