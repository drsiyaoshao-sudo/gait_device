"use client";

export default function CTA() {
  return (
    <section id="contact" className="py-24 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full bg-accent/8 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-3xl px-6 text-center">
        <span className="inline-block rounded-full bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent-light tracking-wide uppercase mb-6">
          Early Access
        </span>
        <h2 className="text-3xl md:text-5xl font-bold text-white">
          Stop debugging hardware.
          <br />
          <span className="gradient-text">Start shipping it.</span>
        </h2>
        <p className="mt-6 text-lg text-slate-400 leading-relaxed">
          We&apos;re working with early design partners building medical devices,
          IoT sensors, and robotics platforms. If you&apos;re tired of the
          hardware-software death spiral, let&apos;s talk.
        </p>

        <form
          className="mt-10 flex flex-col sm:flex-row gap-3 max-w-lg mx-auto"
          onSubmit={(e) => e.preventDefault()}
        >
          <input
            type="email"
            placeholder="you@company.com"
            className="flex-1 rounded-full bg-surface border border-white/10 px-6 py-3.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/50 transition-all"
          />
          <button
            type="submit"
            className="rounded-full bg-accent px-8 py-3.5 text-sm font-medium text-white hover:bg-accent-light transition-colors whitespace-nowrap"
          >
            Get Early Access
          </button>
        </form>

        <p className="mt-4 text-xs text-slate-500">
          No spam. We&apos;ll reach out to discuss your use case.
        </p>

        {/* Trust signals */}
        <div className="mt-16 grid grid-cols-3 gap-8">
          {[
            {
              value: "7",
              label: "Simulation layers",
            },
            {
              value: "13",
              label: "Pre-fab bugs caught",
            },
            {
              value: "0",
              label: "Hardware iterations",
            },
          ].map((stat) => (
            <div key={stat.label}>
              <div className="text-2xl font-bold gradient-text">
                {stat.value}
              </div>
              <div className="text-xs text-slate-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
