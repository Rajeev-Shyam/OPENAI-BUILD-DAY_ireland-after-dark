"use client";

import { useEffect, useRef } from "react";
import { Map as MapLibreMap } from "maplibre-gl";

// Dublin city centre as the starting view; routing coverage widens later.
const DUBLIN_CENTRE: [number, number] = [-6.2603, 53.3498];

export default function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: DUBLIN_CENTRE,
      zoom: 13,
    });

    return () => map.remove();
  }, []);

  return <div ref={containerRef} className="absolute inset-x-0 top-12 bottom-0" />;
}
