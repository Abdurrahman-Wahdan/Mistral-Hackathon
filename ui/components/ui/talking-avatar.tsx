"use client";

import { useEffect, useRef, useImperativeHandle, forwardRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface TalkingAvatarRef {
    startSpeaking: (durationMs: number) => void;
    stopSpeaking: () => void;
}

interface TalkingAvatarProps {
    className?: string;
    onReady?: () => void;
}

export const TalkingAvatar = forwardRef<TalkingAvatarRef, TalkingAvatarProps>(
    ({ className, onReady }, ref) => {
        const iframeRef = useRef<HTMLIFrameElement>(null);
        const [isReady, setIsReady] = useState(false);

        useEffect(() => {
            const handleMessage = (event: MessageEvent) => {
                if (event.data?.type === "avatar_ready") {
                    setIsReady(true);
                    onReady?.();
                }
            };
            window.addEventListener("message", handleMessage);
            return () => window.removeEventListener("message", handleMessage);
        }, [onReady]);

        useImperativeHandle(ref, () => ({
            startSpeaking: (durationMs: number) => {
                if (iframeRef.current?.contentWindow) {
                    iframeRef.current.contentWindow.postMessage(
                        { type: "speak", durationMs },
                        "*"
                    );
                }
            },
            stopSpeaking: () => {
                if (iframeRef.current?.contentWindow) {
                    iframeRef.current.contentWindow.postMessage({ type: "stop" }, "*");
                }
            },
        }));

        return (
            <div className={cn("relative w-full h-full", className)}>
                {!isReady && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-8 h-8 rounded-full border-t-2 border-primary animate-spin" />
                    </div>
                )}
                <iframe
                    ref={iframeRef}
                    src="/avatar.html"
                    title="Talking Avatar"
                    className={cn(
                        "w-full h-full border-none bg-transparent transition-opacity duration-500 rounded-full",
                        isReady ? "opacity-100" : "opacity-0"
                    )}
                    style={{ background: "transparent" }}
                    allow="autoplay; fullscreen"
                />
            </div>
        );
    }
);

TalkingAvatar.displayName = "TalkingAvatar";
