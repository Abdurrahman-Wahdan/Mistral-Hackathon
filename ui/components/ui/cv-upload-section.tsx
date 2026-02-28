"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileUploadCard, UploadedFile } from "@/components/ui/file-upload-card";
import { Button } from "@/components/ui/button";

interface CvUploadSectionProps {
  jobTitle: string;
  onBack: () => void;
  onSubmit: () => void;
}

export default function CvUploadSection({ jobTitle, onBack, onSubmit }: CvUploadSectionProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      const section = sectionRef.current;
      if (!section) return;
      const rect = section.getBoundingClientRect();
      const visibleHeight = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
      setIsVisible(visibleHeight / rect.height > 0.3);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    const uploadingFile = files.find((f) => f.status === "uploading");
    if (!uploadingFile) return;

    const interval = setInterval(() => {
      setFiles((prev) =>
        prev.map((f) => {
          if (f.id === uploadingFile.id) {
            const newProgress = Math.min(f.progress + 10, 100);
            return {
              ...f,
              progress: newProgress,
              status: newProgress === 100 ? "completed" : "uploading",
            };
          }
          return f;
        })
      );
    }, 200);

    return () => clearInterval(interval);
  }, [files]);

  const handleFilesChange = (newFiles: File[]) => {
    const file = newFiles[0];
    if (!file) return;
    setFiles([
      {
        id: `${file.name}-${Date.now()}`,
        file,
        progress: 0,
        status: "uploading",
      },
    ]);
  };

  const handleFileRemove = (id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const handleBack = () => {
    setIsVisible(false);
    onBack();
  };

  return (
    <section
      ref={sectionRef}
      id="cv-upload"
      className="relative h-screen flex items-center justify-center px-6"
    >
      <div className="flex flex-col items-center">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
          className="text-center mb-10"
        >
          <motion.h2
            className="text-3xl sm:text-4xl font-bold text-foreground mb-3"
            initial={{ opacity: 0, y: -10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            Apply for {jobTitle}
          </motion.h2>
          <motion.p
            className="text-foreground/40 text-lg"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.25 }}
          >
            Upload your CV to complete your application
          </motion.p>
        </motion.div>

        <FileUploadCard
          files={files}
          onFilesChange={handleFilesChange}
          onFileRemove={handleFileRemove}
        />
      </div>

      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed bottom-8 left-8 z-50"
          >
            <Button
              size="lg"
              variant="outline"
              className="group h-auto border-white/20 text-foreground hover:bg-white/10 transition-all duration-300 backdrop-blur-xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
              onClick={handleBack}
            >
              <span className="relative block">
                <span className="block transition-opacity duration-300 group-hover:opacity-0">Back</span>
                <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&larr;</span>
              </span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {files.some((f) => f.status === "completed") && isVisible && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ duration: 0.3, type: "spring", stiffness: 200 }}
            className="fixed bottom-8 right-8 z-50"
          >
            <Button
              size="lg"
              className="group h-auto bg-white text-black hover:bg-white/90 transition-all duration-300 shadow-2xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
              onClick={onSubmit}
            >
              <span className="relative block">
                <span className="block transition-opacity duration-300 group-hover:opacity-0">Submit</span>
                <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&rarr;</span>
              </span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
