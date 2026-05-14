"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { createResume } from "@/lib/api";
import { toast } from "sonner";

export function NewResumeButton() {
  const router = useRouter();
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      const { id } = await createResume();
      router.push(`/editor/${id}`);
    } catch (error) {
      console.error("Failed to create resume:", error);
      toast.error("Failed to create resume. Please try again.");
      setIsCreating(false);
    }
  };

  return (
    <Button onClick={handleCreate} disabled={isCreating} size="lg">
      {isCreating ? "Creating..." : "New Resume"}
    </Button>
  );
}
