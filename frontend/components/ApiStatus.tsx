"use client";

import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ApiStatus() {
  const [label, setLabel] = useState("checking API…");

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE_URL}/health`)
      .then((response) => response.json())
      .then((body: { mongo_connected: boolean }) => {
        if (cancelled) return;
        setLabel(body.mongo_connected ? "API: connected (Mongo up)" : "API: connected (Mongo down)");
      })
      .catch(() => {
        if (!cancelled) setLabel("API: unreachable — start the backend on :8000");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return <span className="text-sm opacity-80">{label}</span>;
}
