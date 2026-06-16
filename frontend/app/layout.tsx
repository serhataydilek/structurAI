import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Structura AI",
  description: "From building photos to interactive digital twins."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
