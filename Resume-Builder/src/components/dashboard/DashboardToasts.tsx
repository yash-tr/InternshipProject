"use client";

import { useEffect } from "react";
import { toast } from "sonner";

interface DashboardToastsProps {
  resumeNotFound?: boolean;
}

export function DashboardToasts({ resumeNotFound }: DashboardToastsProps) {
  useEffect(() => {
    if (resumeNotFound) {
      toast.error("Resume not found");
    }
  }, [resumeNotFound]);

  return null;
}

