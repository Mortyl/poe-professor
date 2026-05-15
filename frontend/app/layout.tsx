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
    <html lang="en">
      <body>
        {children}
        <CompanionGate />
      </body>
    </html>
  );
}
