import * as React from "react";
import { UploadCloud, X, CheckCircle2, Trash2, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export interface UploadedFile {
  id: string;
  file: File;
  progress: number;
  status: "uploading" | "completed" | "error";
}

interface FileUploadCardProps extends React.HTMLAttributes<HTMLDivElement> {
  files: UploadedFile[];
  onFilesChange: (files: File[]) => void;
  onFileRemove: (id: string) => void;
  onClose?: () => void;
}

export const FileUploadCard = React.forwardRef<HTMLDivElement, FileUploadCardProps>(
  ({ className, files = [], onFilesChange, onFileRemove, onClose }, ref) => {
    const [isDragging, setIsDragging] = React.useState(false);
    const fileInputRef = React.useRef<HTMLInputElement>(null);

    const handleDragEnter = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      const droppedFiles = Array.from(e.dataTransfer.files);
      if (droppedFiles && droppedFiles.length > 0) {
        onFilesChange([droppedFiles[0]]);
      }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(e.target.files || []);
      if (selectedFiles.length > 0) {
        onFilesChange([selectedFiles[0]]);
      }
      // Reset input so the same file can be re-selected after deletion
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    };

    const triggerFileSelect = () => fileInputRef.current?.click();

    const formatFileSize = (bytes: number) => {
      if (bytes === 0) return "0 KB";
      const k = 1024;
      const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const hasFile = files.length > 0;

    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 0, scale: 0.95, y: 30 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
        className={cn(
          "w-full max-w-md rounded-2xl bg-white/[0.03] backdrop-blur-2xl",
          "border border-white/10 shadow-[0_0_40px_rgba(255,255,255,0.03)]",
          className
        )}
      >
        <div className="p-8">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
            className="flex items-center gap-4 mb-8"
          >
            <motion.div
              className="w-12 h-12 flex items-center justify-center rounded-full bg-white/[0.06] border border-white/10"
              whileHover={{ scale: 1.05 }}
            >
              <UploadCloud className="w-5 h-5 text-foreground/50" />
            </motion.div>
            <div className="flex-1">
              <h3 className="text-base font-semibold text-foreground">Upload your CV</h3>
              <p className="text-sm text-foreground/40 mt-0.5">
                PDF or DOCX, up to 10 MB
              </p>
            </div>
            {onClose && (
              <Button variant="ghost" size="icon" className="rounded-full w-8 h-8 text-foreground/40 hover:text-foreground hover:bg-white/10" onClick={onClose}>
                <X className="w-4 h-4" />
              </Button>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={triggerFileSelect}
            className={cn(
              "border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center text-center transition-all duration-300 cursor-pointer",
              isDragging
                ? "border-white/40 bg-white/[0.06] scale-[1.02]"
                : "border-white/10 hover:border-white/25 hover:bg-white/[0.02]"
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx"
              className="hidden"
              onChange={handleFileSelect}
            />
            <motion.div
              animate={isDragging ? { scale: 1.1, y: -5 } : { scale: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <UploadCloud className="w-8 h-8 text-foreground/30 mb-4 mx-auto" />
            </motion.div>
            <p className="font-medium text-foreground/80 text-sm">
              {isDragging ? "Drop your file here" : "Drag & drop or click to browse"}
            </p>
            <p className="text-xs text-foreground/30 mt-2">
              PDF and DOCX formats accepted
            </p>
          </motion.div>
        </div>

        <AnimatePresence mode="wait">
          {hasFile && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
              className="overflow-hidden"
            >
              <div className="px-8 pb-8 pt-2">
                <div className="border-t border-white/[0.06] pt-5">
                  <AnimatePresence>
                    {files.map((file) => (
                      <motion.div
                        key={file.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        transition={{ duration: 0.3 }}
                        className="flex items-center gap-3"
                      >
                        <motion.div
                          className="w-10 h-10 flex items-center justify-center rounded-lg bg-white/[0.06] border border-white/10"
                          initial={{ scale: 0.8 }}
                          animate={{ scale: 1 }}
                          transition={{ delay: 0.1, type: "spring", stiffness: 200 }}
                        >
                          <FileText className="w-4 h-4 text-foreground/50" />
                        </motion.div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground truncate">{file.file.name}</p>
                          <div className="flex items-center gap-1.5 text-xs text-foreground/35 mt-0.5">
                            <span>{formatFileSize(file.file.size)}</span>
                            <span>&middot;</span>
                            <motion.span
                              className={cn(
                                file.status === "uploading" && "text-foreground/50",
                                file.status === "completed" && "text-green-400",
                              )}
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                            >
                              {file.status === "uploading" ? `${file.progress}%` : "Ready"}
                            </motion.span>
                          </div>
                          {file.status === "uploading" && (
                            <motion.div
                              initial={{ opacity: 0, scaleX: 0 }}
                              animate={{ opacity: 1, scaleX: 1 }}
                              className="origin-left"
                            >
                              <Progress value={file.progress} className="h-1 mt-2 bg-white/[0.06]" />
                            </motion.div>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {file.status === "completed" && (
                            <motion.div
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              transition={{ type: "spring", stiffness: 300, delay: 0.1 }}
                            >
                              <CheckCircle2 className="w-4 h-4 text-green-400" />
                            </motion.div>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="rounded-full w-7 h-7 text-foreground/30 hover:text-foreground hover:bg-white/10"
                            onClick={(e) => {
                              e.stopPropagation();
                              onFileRemove(file.id);
                            }}
                          >
                            {file.status === "completed" ? <Trash2 className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
                          </Button>
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  }
);
FileUploadCard.displayName = "FileUploadCard";
