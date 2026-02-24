import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SRE-Agent | AI-Powered Incident Investigation",
  description: "Autonomous troubleshooting with human-in-the-loop",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gray-950 text-white antialiased">
        {children}
      </body>
    </html>
  );
}
