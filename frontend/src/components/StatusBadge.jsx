import React from "react";

const STATUS_LABELS = {
  completed: "Completed",
  processing: "Processing",
  failed: "Failed",
  duplicate: "Duplicate — Ignored"
};

export default function StatusBadge({ status }) {
  const normalized = status || "processing";
  return (
    <span className={`status-badge ${normalized}`}>
      {STATUS_LABELS[normalized] || normalized}
    </span>
  );
}
