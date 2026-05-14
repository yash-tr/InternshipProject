"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

type Result = string | string[];

interface AIAssistButtonProps {
  onGenerate: () => Promise<Result>;
  onAccept: (result: Result) => void;
  label?: string;
  size?: "default" | "sm" | "lg" | "icon";
  variant?:
    | "default"
    | "secondary"
    | "outline"
    | "ghost"
    | "link"
    | "destructive";
  /** When true and result is string[], show checkboxes and pass only selected to onAccept */
  pickMultiple?: boolean;
}

export function AIAssistButton({
  onGenerate,
  onAccept,
  label = "Generate with AI",
  size = "sm",
  variant = "secondary",
  pickMultiple = false,
}: AIAssistButtonProps) {
  const [state, setState] = useState<"idle" | "loading" | "suggestion">("idle");
  const [suggestion, setSuggestion] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const handleGenerate = async () => {
    setState("loading");
    setError(null);
    setSuggestion(null);
    setSelected(new Set());
    try {
      const result = await onGenerate();
      setSuggestion(result);
      if (pickMultiple && Array.isArray(result)) {
        setSelected(new Set(result.map((_, i) => i)));
      }
      setState("suggestion");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      toast.error("AI is unavailable, please try again");
      setState("idle");
    }
  };

  const handleAccept = () => {
    if (suggestion == null) return;
    if (pickMultiple && Array.isArray(suggestion)) {
      const chosen = suggestion.filter((_, i) => selected.has(i));
      if (chosen.length) onAccept(chosen);
    } else {
      onAccept(suggestion);
    }
    setSuggestion(null);
    setState("idle");
  };

  const handleDiscard = () => {
    setSuggestion(null);
    setState("idle");
  };

  const toggleSkill = (i: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  const isArray = Array.isArray(suggestion);
  const text = !isArray ? (suggestion as string) : null;
  const list = isArray ? (suggestion as string[]) : null;

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant={variant}
        size={size}
        onClick={handleGenerate}
        disabled={state === "loading"}
      >
        {state === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Sparkles className="h-4 w-4" />
        )}
        {label && (
          <span className={size === "icon" ? "sr-only" : "ml-1.5"}>
            {label}
          </span>
        )}
      </Button>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {state === "suggestion" && suggestion != null && (
        <div className="rounded-lg border-2 border-primary/30 bg-primary/5 p-3 space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            {pickMultiple && list ? "Pick skills to add" : "Suggestion"}
          </p>
          {text !== null && (
            <p className="text-sm whitespace-pre-wrap">{text}</p>
          )}
          {list !== null && !pickMultiple && (
            <ul className="text-sm list-disc list-inside space-y-0.5">
              {list.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
          {list !== null && pickMultiple && (
            <ul className="text-sm space-y-1.5 max-h-48 overflow-y-auto">
              {list.map((s, i) => (
                <li key={i} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id={`ai-skill-${i}`}
                    checked={selected.has(i)}
                    onChange={() => toggleSkill(i)}
                    className="h-4 w-4 rounded border"
                  />
                  <label htmlFor={`ai-skill-${i}`} className="cursor-pointer">
                    {s}
                  </label>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-2 pt-1">
            <Button type="button" size="sm" onClick={handleAccept}>
              {pickMultiple && list ? "Add selected" : "Use this"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleDiscard}
            >
              Discard
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

