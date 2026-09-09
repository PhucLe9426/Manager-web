"use client";

import { CircleHelp } from "lucide-react";

export function MetricHelp({ text, label = "Giải thích chỉ số" }: { text: string; label?: string }) {
  return <span className="metric-help-wrap">
    <button type="button" className="metric-help" aria-label={`${label}: ${text}`} data-tooltip={text}>
      <CircleHelp size={14} aria-hidden="true" />
    </button>
  </span>;
}
