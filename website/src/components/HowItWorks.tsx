import SectionHeading from "./SectionHeading";

const layers = [
  {
    num: 1,
    name: "Walker Model",
    tech: "Python + NumPy",
    description: "Physical signal generation from first-order biomechanical primitives",
    color: "bg-accent",
  },
  {
    num: 2,
    name: "IMU Quantization",
    tech: "Sensor Modeling",
    description: "16-bit quantization at real sensor sensitivity (LSM6DS3 FIFO format)",
    color: "bg-accent-light",
  },
  {
    num: 3,
    name: "I2C Peripheral Stub",
    tech: "Renode Python API",
    description: "Emulated sensor registers, FIFO queue, and hardware interrupts",
    color: "bg-emerald",
  },
  {
    num: 4,
    name: "Full-System Emulation",
    tech: "Cortex-M4F in Renode",
    description: "Real firmware ELF executing on cycle-accurate ARM emulator",
    color: "bg-emerald-light",
  },
  {
    num: 5,
    name: "UART Capture",
    tech: "Signal Analysis",
    description: "Structured firmware output parsed into typed diagnostic events",
    color: "bg-gold",
  },
  {
    num: 6,
    name: "Snapshot Export",
    tech: "BLE GATT",
    description: "Binary snapshot buffer with session management and wireless export",
    color: "bg-gold-light",
  },
  {
    num: 7,
    name: "Visualization",
    tech: "Streamlit + Plotly",
    description: "Interactive dashboards comparing Python reference vs. firmware output",
    color: "bg-rose",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 relative">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeading
          tag="How It Works"
          title="The 7-layer digital twin"
          subtitle="Each layer owns exactly one transformation. Never collapse layers — clean boundaries make bugs visible and fixes surgical."
        />

        {/* Pipeline visualization */}
        <div className="relative">
          {/* Vertical line connector */}
          <div className="hidden md:block absolute left-[39px] top-0 bottom-0 w-px bg-gradient-to-b from-accent via-emerald to-rose opacity-30" />

          <div className="space-y-4">
            {layers.map((layer) => (
              <div key={layer.num} className="flex items-start gap-6 group">
                {/* Number circle */}
                <div
                  className={`flex-shrink-0 w-[78px] h-[78px] rounded-2xl ${layer.color} flex items-center justify-center text-white font-bold text-xl shadow-lg group-hover:scale-110 transition-transform`}
                >
                  L{layer.num}
                </div>

                {/* Content card */}
                <div className="flex-1 glass rounded-2xl p-6 group-hover:border-white/20 transition-colors">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                    <h3 className="text-lg font-semibold text-white">
                      {layer.name}
                    </h3>
                    <span className="text-xs font-mono text-slate-500 bg-white/5 px-2 py-1 rounded">
                      {layer.tech}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">
                    {layer.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Development order */}
        <div className="mt-16 glass rounded-2xl p-8">
          <h3 className="text-sm font-medium text-accent-light uppercase tracking-wide mb-4">
            Fixed development order
          </h3>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {[
              "Firmware",
              "Software",
              "Simulation",
              "Edge Cases",
              "Hardware",
            ].map((stage, i) => (
              <div key={stage} className="flex items-center gap-3">
                <span className="bg-surface-light rounded-lg px-4 py-2 text-white font-medium">
                  {i + 1}. {stage}
                </span>
                {i < 4 && (
                  <svg
                    className="w-4 h-4 text-slate-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                )}
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-slate-500">
            Every step must be confirmed correct before advancing. Hardware is
            expensive to debug — everything before it is not.
          </p>
        </div>
      </div>
    </section>
  );
}
