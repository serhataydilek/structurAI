import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Structura AI",
  description: "Local capture to COLMAP sparse point cloud previews."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
