"use client";

import { useState, useEffect } from "react";
import ShaperCompanion from "./ShaperCompanion";

export default function CompanionGate() {
  const [chosen, setChosen] = useState(false);

  useEffect(() => {
    const check = () => setChosen(!!localStorage.getItem("poe_companion"));
    check();
    // Re-check whenever another part of the app sets the companion
    window.addEventListener("poe_companion_selected", check);
    return () => window.removeEventListener("poe_companion_selected", check);
  }, []);

  if (!chosen) return null;
  return <ShaperCompanion />;
}
