import type { Metadata } from "next";
import "./globals.css";
import CompanionGate from "./components/CompanionGate";

export const metadata: Metadata = {
  title: "PoEProfessor",
  description: "Path of Exile 2 companion tool — AI build guides, atlas strategy, crafting and character optimisation",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <head>
        {/* Google Fonts via <link> — Turbopack strips @import from globals.css,
            which left every Cinzel/EB Garamond reference falling back to serif. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Rajdhani:wght@300;400;500;600;700&family=Share+Tech+Mono&display=swap"
        />
      </head>
      <body>
        {children}
        <CompanionGate />
      </body>
    </html>
  );
}
