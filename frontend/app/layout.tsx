import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Plant Docs Assistant",
  description: "Ask questions about plant safety, maintenance and quality documents",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

const themeScript = `(function(){var d=document.documentElement,m=matchMedia('(prefers-color-scheme: dark)');function s(){try{return localStorage.getItem('theme')}catch(e){return null}}function a(){var t=s();d.classList.toggle('dark',t?t==='dark':m.matches)}a();m.addEventListener('change',a)})()`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full">
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {children}
      </body>
    </html>
  );
}
