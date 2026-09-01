import "./globals.css";

export const metadata = {
  title: "Concierge — Agentic Commerce",
  description: "Concierge agentic commerce demo"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}