import Link from "next/link";
import Navbar from "../components/Navbar";

export default function AtlasPage() {
  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 56px)", background: "#07070f", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 24px", textAlign: "center" }}>
        <p style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "11px", letterSpacing: "0.2em", textTransform: "uppercase", color: "#4a4a6a", marginBottom: "20px" }}>
          Coming Soon
        </p>
        <h1 style={{ fontFamily: "'Cinzel', serif", fontSize: "clamp(28px, 4vw, 44px)", fontWeight: 700, color: "#e8d4a8", letterSpacing: "0.06em", marginBottom: "16px" }}>
          Atlas Designer
        </h1>
        <p style={{ fontFamily: "'Rajdhani', sans-serif", fontSize: "15px", color: "#4a4a6a", maxWidth: "480px", lineHeight: 1.7, marginBottom: "40px" }}>
          Tell me what you want to farm and I will generate the optimal atlas passive strategy to get you there. Under construction.
        </p>
        <Link href="/" style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: "11px", letterSpacing: "0.12em", textTransform: "uppercase", color: "#c8963c", textDecoration: "none" }}>
          ← Back to Home
        </Link>
      </main>
    </>
  );
}
