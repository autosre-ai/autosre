import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "OpenSRE | AI-Powered Incident Response",
  description: "Autonomous incident investigation with human-in-the-loop approval",
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gray-950 text-white antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
