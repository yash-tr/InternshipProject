"use client";

import { PDFDownloadLink } from "@react-pdf/renderer";
import { Button } from "@/components/ui/button";
import { PDFClassic } from "./PDFClassic";
import { PDFModern } from "./PDFModern";
import { PDFPremium } from "./PDFPremium";
import type { ResumeData } from "@appTypes/resume";

interface PDFDownloadButtonProps {
  data: ResumeData;
  templateId: string;
}

const templates = {
  classic: PDFClassic,
  modern: PDFModern,
  premium: PDFPremium,
} as const;

export function PDFDownloadButton({ data, templateId }: PDFDownloadButtonProps) {
  const Doc =
    templates[templateId as keyof typeof templates] ?? templates.classic;

  return (
    <PDFDownloadLink
      document={<Doc data={data} />}
      fileName="resume.pdf"
    >
      {({ loading }) => (
        <Button variant="outline" size="sm" disabled={loading}>
          {loading ? "Generating…" : "Download PDF"}
        </Button>
      )}
    </PDFDownloadLink>
  );
}
