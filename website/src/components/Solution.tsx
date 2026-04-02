import SectionHeading from "./SectionHeading";

const pillars = [
  {
    number: "01",
    title: "Physics-Native Simulation",
    description:
      "We don't inject sensor readings — we inject first-order physical quantities. Our digital twin starts from biomechanics, electromagnetics, or thermodynamics and derives every signal from ground truth.",
    color: "accent",
  },
  {
    number: "02",
    title: "Instruction-Level Validation",
    description:
      "Your actual C firmware runs on an emulated Cortex-M4F inside our pipeline. Not a mock, not a model — the real ELF binary, executing real ARM instructions on a cycle-accurate simulator.",
    color: "emerald",
  },
  {
    number: "03",
    title: "Deterministic Regression",
    description:
      "Every known failure mode becomes an automated test. When you change the algorithm, every edge case is re-verified in minutes — not after weeks of field testing.",
    color: "gold",
  },
];

export default function Solution() {
  return (
    <section id="solution" className="py-24 relative">
      {/* Background accent */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] rounded-full bg-accent/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl px-6">
        <SectionHeading
          tag="The Solution"
          title="CI/CD for hardware"
          subtitle="Crucible brings the speed and reliability of modern software development to hardware. Catch every bug before you ever power on a prototype."
        />

        <div className="grid md:grid-cols-3 gap-6">
          {pillars.map((pillar) => (
            <div
              key={pillar.number}
              className="glass rounded-2xl p-8 relative overflow-hidden group hover:border-accent/30 transition-all"
            >
              <span
                className={`text-6xl font-bold opacity-10 absolute -top-2 -right-2 text-${pillar.color}`}
              >
                {pillar.number}
              </span>
              <div className="relative">
                <h3 className="text-lg font-semibold text-white">
                  {pillar.title}
                </h3>
                <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                  {pillar.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Key differentiator */}
        <div className="mt-16 glass rounded-2xl p-8 md:p-12 text-center">
          <p className="text-lg md:text-xl text-white font-medium leading-relaxed">
            &ldquo;We found and fixed a{" "}
            <span className="text-rose font-bold">critical safety bug</span>{" "}
            that would have caused our medical device to report{" "}
            <span className="text-rose font-bold">
              perfect symmetry for every patient
            </span>
            . We caught it in simulation —{" "}
            <span className="text-emerald font-bold">
              before fabricating a single board
            </span>
            .&rdquo;
          </p>
          <p className="mt-4 text-sm text-slate-500">
            BUG-013 — ARM FPU instruction VABS.F32 broken in emulator, silently
            zeroing all symmetry measurements
          </p>
        </div>
      </div>
    </section>
  );
}
