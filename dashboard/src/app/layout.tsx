import type { Metadata, Viewport } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "CAMINA — Urban mobility counter",
  description: "Privacy-preserving street-level mobility counts for Dublin.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#000000",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-black antialiased">{children}</body>
    </html>
  );
}
