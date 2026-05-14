"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { deleteResume } from "@/lib/api";
import type { Resume } from "@/lib/api";

interface ResumeCardProps {
  resume: Resume;
}

export function ResumeCard({ resume }: ResumeCardProps) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteResume(resume.id);
      setIsDialogOpen(false);
      router.refresh();
    } catch (error) {
      console.error("Failed to delete resume:", error);
      alert("Failed to delete resume. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  const isPro = resume.templateId === "pro" || resume.templateId?.includes("pro");
  const updatedAt = resume.updatedAt ? new Date(resume.updatedAt) : new Date();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{resume.title || "Untitled Resume"}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Badge variant={isPro ? "default" : "secondary"}>
            {isPro ? "Pro" : "Free"}
          </Badge>
          <span className="text-xs text-muted-foreground">
            Updated {formatDistanceToNow(updatedAt, { addSuffix: true })}
          </span>
        </div>
      </CardContent>
      <CardFooter className="flex gap-2">
        <Button asChild variant="outline" className="flex-1">
          <Link href={`/editor/${resume.id}`}>Edit</Link>
        </Button>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive" disabled={isDeleting}>
              {isDeleting ? "Deleting..." : "Delete"}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Resume</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "{resume.title || "Untitled Resume"}"? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardFooter>
    </Card>
  );
}
