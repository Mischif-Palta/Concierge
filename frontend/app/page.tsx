export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-950 text-white">
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center px-6 text-center">
        <div className="mb-6 rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-400">
          Concierge • AI Commerce Assistant
        </div>

        <h1 className="text-5xl font-bold tracking-tight sm:text-6xl">
          Concierge
        </h1>

        <p className="mt-6 max-w-2xl text-lg leading-8 text-zinc-400">
          An AI-powered commerce assistant that helps customers discover
          products, manage their shopping experience, and complete purchases
          through conversational interactions.
        </p>

        <div className="mt-10 flex gap-4">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-3 text-sm">
            AI Powered
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-3 text-sm">
            Secure Payments
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-900 px-5 py-3 text-sm">
            Agentic Commerce
          </div>
        </div>

        <p className="mt-12 text-sm text-zinc-600">
          Prototype • Built for demonstration purposes
        </p>
      </div>
    </main>
  );
}