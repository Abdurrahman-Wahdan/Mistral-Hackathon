"use client";

import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import type { FinishInterviewResponse, InterviewReviewPayload } from "@/lib/interview-review-types";

interface GeneratingReportScreenProps {
    jobTitle: string;
    sessionId: string;
    onReady: (reviewPayload: InterviewReviewPayload) => void;
    onBack?: () => void;
    onRetry?: () => void;
}

export default function GeneratingReportScreen({
    jobTitle,
    sessionId,
    onReady,
    onBack,
    onRetry,
}: GeneratingReportScreenProps) {
    const [stage, setStage] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [isFinished, setIsFinished] = useState(false);
    const [reviewPayload, setReviewPayload] = useState<InterviewReviewPayload | null>(null);
    const [retryNonce, setRetryNonce] = useState(0);
    const hasFinishedRef = useRef(false);

    useEffect(() => {
        const t1 = setTimeout(() => setStage(1), 600);
        const t2 = setTimeout(() => setStage(2), 1800);
        const t3 = setTimeout(() => setStage(3), 3200);
        return () => {
            clearTimeout(t1);
            clearTimeout(t2);
            clearTimeout(t3);
        };
    }, []);

    useEffect(() => {
        if (hasFinishedRef.current) return;
        hasFinishedRef.current = true;

        const finishInterview = async () => {
            try {
                const response = await fetch("/api/interview-session/finish", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sessionId, jobTitle, force: true }),
                });
                const payload = (await response.json().catch(() => null)) as FinishInterviewResponse | null;

                if (!response.ok) {
                    throw new Error("Unable to finalize the interview session");
                }

                if (!payload?.review) {
                    throw new Error("Interview finished, but review payload is missing.");
                }

                setReviewPayload(payload.review);
                setIsFinished(true);
            } catch (err) {
                console.error("[GeneratingReportScreen] Finalize failed:", err);
                setError("Report generation failed. Please try again.");
            }
        };

        void finishInterview();
    }, [sessionId, jobTitle, retryNonce]);

    // Proceed when animation is done (stage >= 3) AND backend is ready
    useEffect(() => {
        if (stage >= 3 && isFinished && !error && reviewPayload) {
            onReady(reviewPayload);
        }
    }, [stage, isFinished, error, onReady, reviewPayload]);

    const handleRetry = () => {
        setError(null);
        setIsFinished(false);
        setReviewPayload(null);
        hasFinishedRef.current = false;
        setRetryNonce((value) => value + 1);
        onRetry?.();
    };

    return (
        <section className="fixed inset-0 z-50 flex items-center justify-center bg-black">
            <div className="flex flex-col items-center text-center px-6 max-w-2xl">
                <AnimatePresence>
                    {stage >= 0 && (
                        <motion.h2
                            key="heading"
                            initial={{ opacity: 0, filter: "blur(20px)" }}
                            animate={{ opacity: 1, filter: "blur(0px)" }}
                            transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
                            className="text-3xl sm:text-4xl lg:text-5xl font-bold text-foreground mb-6"
                        >
                            Generating Your Report
                        </motion.h2>
                    )}
                </AnimatePresence>

                <AnimatePresence>
                    {stage >= 1 && (
                        <motion.p
                            key="subtitle"
                            initial={{ opacity: 0, filter: "blur(16px)" }}
                            animate={{ opacity: 1, filter: "blur(0px)" }}
                            transition={{ duration: 1, ease: [0.25, 0.1, 0.25, 1] }}
                            className="text-lg sm:text-xl text-foreground/50 mb-4"
                        >
                            Finalizing interview for{" "}
                            <span className="text-foreground/80 font-medium">{jobTitle}</span>
                        </motion.p>
                    )}
                </AnimatePresence>

                <AnimatePresence>
                    {stage >= 2 && (
                        <motion.p
                            key="detail"
                            initial={{ opacity: 0, filter: "blur(12px)" }}
                            animate={{ opacity: 1, filter: "blur(0px)" }}
                            transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
                            className="text-base text-foreground/30 mb-10"
                        >
                            Processing transcript logs, generating AI analysis, and preparing your final dashboard...
                        </motion.p>
                    )}
                </AnimatePresence>

                <AnimatePresence>
                    {stage >= 3 && !error && (
                        <motion.div
                            key="dots"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.5 }}
                            className="flex gap-2"
                        >
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    className="w-2 h-2 rounded-full bg-foreground/30"
                                    animate={{ opacity: [0.3, 1, 0.3] }}
                                    transition={{
                                        duration: 1.4,
                                        repeat: Infinity,
                                        delay: i * 0.2,
                                        ease: "easeInOut",
                                    }}
                                />
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>

                {!error && (
                    <div className="mt-8 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-white/10">
                        <motion.div
                            className="h-full rounded-full bg-white/85"
                            initial={{ width: "18%" }}
                            animate={{ width: stage >= 3 ? "92%" : stage === 2 ? "70%" : stage === 1 ? "44%" : "18%" }}
                            transition={{ duration: 0.55, ease: "easeOut" }}
                        />
                    </div>
                )}

                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-8 w-full rounded-2xl border border-red-400/30 bg-red-500/10 p-5"
                    >
                        <p className="text-sm text-red-100/90 mb-5">{error}</p>
                        <div className="flex flex-wrap items-center justify-center gap-3">
                            {onBack && (
                                <Button
                                    variant="outline"
                                    className="border-white/20 bg-transparent text-foreground hover:bg-white/10"
                                    onClick={onBack}
                                >
                                    Return Home
                                </Button>
                            )}
                            {onRetry && (
                                <Button className="bg-white text-black hover:bg-white/90" onClick={handleRetry}>
                                    Retry Generation
                                </Button>
                            )}
                        </div>
                    </motion.div>
                )}
            </div>
        </section>
    );
}
