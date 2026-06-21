import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Structura AI",
  description: "RealityScan-first model generation with optional COLMAP validation."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
