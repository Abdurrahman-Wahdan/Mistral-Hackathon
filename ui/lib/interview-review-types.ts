export interface InterviewReportFile {
  id: string;
  fileName: string;
  createdAt: string;
  mimeType: string;
  content: string;
}

export interface InterviewPhaseScore {
  name: string;
  score: number;
}

export interface InterviewDetailedMetric {
  label: string;
  score: number;
  feedback: string;
}

export interface InterviewReviewPayload {
  summary: string;
  analysisHighlights: string[];
  overallScore: number;
  strengths: string[];
  weaknesses: string[];
  phases: InterviewPhaseScore[];
  detailedMetrics: InterviewDetailedMetric[];
  report: InterviewReportFile;
}

export interface FinishInterviewResponse {
  session_id: string;
  summary: unknown;
  review: InterviewReviewPayload;
}
