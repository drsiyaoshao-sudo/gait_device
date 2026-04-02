export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background gradient orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full bg-gold/5 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-accent/5 blur-3xl" />
      </div>

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative z-10 mx-auto max-w-5xl px-6 text-center pt-32 pb-20">
        <div className="animate-fade-in-up">
          <span className="inline-block rounded-full bg-accent/10 border border-accent/20 px-4 py-1.5 text-xs font-medium text-accent-light tracking-wide uppercase mb-8">
            Introducing Crucible
          </span>
        </div>

        <h1
          className="text-5xl md:text-7xl font-bold leading-tight tracking-tight animate-fade-in-up"
          style={{ animationDelay: "0.1s" }}
        >
          Hardware development
          <br />
          <span className="gradient-text">at the speed of software</span>
        </h1>

        <p
          className="mt-8 max-w-2xl mx-auto text-lg md:text-xl text-slate-400 leading-relaxed animate-fade-in-up"
          style={{ animationDelay: "0.2s" }}
        >
          We eliminate the hardware-software death spiral. Our 7-layer digital
          twin catches critical bugs before you ever fabricate a board — turning
          months of iteration into days.
        </p>

        <div
          className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up"
          style={{ animationDelay: "0.3s" }}
        >
          <a
            href="#contact"
            className="rounded-full bg-accent px-8 py-3.5 text-sm font-medium text-white hover:bg-accent-light transition-all animate-pulse-glow"
          >
            Get Early Access
          </a>
          <a
            href="#case-study"
            className="rounded-full border border-white/15 px-8 py-3.5 text-sm font-medium text-slate-300 hover:border-white/30 hover:text-white transition-all"
          >
            See the Demo
          </a>
        </div>

        {/* Stats bar */}
        <div
          className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-6 animate-fade-in-up"
          style={{ animationDelay: "0.4s" }}
        >
          {[
            { value: "13", label: "Bugs caught in simulation" },
            { value: "0", label: "Hardware prototypes needed" },
            { value: "151", label: "Automated tests passing" },
            { value: "$45", label: "Total BOM cost" },
          ].map((stat) => (
            <div key={stat.label} className="glass rounded-2xl p-5">
              <div className="text-3xl font-bold text-white">{stat.value}</div>
              <div className="mt-1 text-xs text-slate-500">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
