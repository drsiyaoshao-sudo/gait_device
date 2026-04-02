import SectionHeading from "./SectionHeading";

const terrainResults = [
  { terrain: "Flat ground", steps: "100/100", status: "pass" },
  { terrain: "Poor device fit", steps: "100/100", status: "pass" },
  { terrain: "10 deg slope", steps: "100/100", status: "pass" },
  { terrain: "Stairs", steps: "100/100", status: "pass" },
];

const bugHighlights = [
  {
    id: "BUG-010",
    title: "Stair walker: 0 steps detected",
    cause:
      "Dual-confirmation detector assumed heel-strike and gyr_y zero-crossing within 40ms. On stairs, the gap was 135ms.",
    fix: "Terrain-aware push-off primary detector with retrospective heel-strike inference via 8-entry ring buffer.",
    severity: "critical",
  },
  {
    id: "BUG-013",
    title: "SI always reports 0% (perfect symmetry)",
    cause:
      "ARM FPU instruction VABS.F32 broken in Renode 1.16.1 emulator — silently returned 0.0 for all inputs.",
    fix: "Replaced FPU absolute value with conditional branch. Verified: pathological walker now correctly reports 17-24% SI.",
    severity: "safety",
  },
];

export default function CaseStudy() {
  return (
    <section id="case-study" className="py-24 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 right-0 w-[500px] h-[500px] rounded-full bg-emerald/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-7xl px-6">
        <SectionHeading
          tag="Case Study"
          title="GaitSense: from algorithm to validated firmware"
          subtitle="A single-ankle wearable that detects walking asymmetry. Built entirely in simulation — zero hardware prototypes, 13 bugs caught before fabrication."
        />

        {/* Device specs */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
          {[
            { label: "Processor", value: "nRF52840" },
            { label: "Sensor", value: "LSM6DS3 IMU" },
            { label: "Battery Life", value: "344 days" },
            { label: "BOM Cost", value: "~$45" },
          ].map((spec) => (
            <div key={spec.label} className="glass rounded-xl p-5 text-center">
              <div className="text-xs text-slate-500 uppercase tracking-wide">
                {spec.label}
              </div>
              <div className="mt-1 text-xl font-bold text-white">
                {spec.value}
              </div>
            </div>
          ))}
        </div>

        {/* Terrain validation table */}
        <div className="glass rounded-2xl overflow-hidden mb-12">
          <div className="p-6 border-b border-white/10">
            <h3 className="text-lg font-semibold text-white">
              Terrain Validation Matrix
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              All 4 terrain profiles validated — 100% step detection across
              healthy and pathological walkers
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-6 text-slate-500 font-medium">
                    Terrain
                  </th>
                  <th className="text-left py-3 px-6 text-slate-500 font-medium">
                    Steps Detected
                  </th>
                  <th className="text-left py-3 px-6 text-slate-500 font-medium">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {terrainResults.map((r) => (
                  <tr
                    key={r.terrain}
                    className="border-b border-white/5 hover:bg-white/5 transition-colors"
                  >
                    <td className="py-3 px-6 text-white">{r.terrain}</td>
                    <td className="py-3 px-6 font-mono text-emerald">
                      {r.steps}
                    </td>
                    <td className="py-3 px-6">
                      <span className="inline-flex items-center gap-1.5 text-emerald text-xs font-medium">
                        <span className="w-2 h-2 rounded-full bg-emerald" />
                        PASS
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Bug highlights */}
        <h3 className="text-lg font-semibold text-white mb-6">
          Critical bugs caught in simulation
        </h3>
        <div className="grid md:grid-cols-2 gap-6">
          {bugHighlights.map((bug) => (
            <div
              key={bug.id}
              className="glass rounded-2xl p-6 border-l-4 border-l-rose"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="font-mono text-sm font-bold text-rose">
                  {bug.id}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    bug.severity === "safety"
                      ? "bg-rose/20 text-rose"
                      : "bg-gold/20 text-gold"
                  }`}
                >
                  {bug.severity.toUpperCase()}
                </span>
              </div>
              <h4 className="text-white font-medium">{bug.title}</h4>
              <div className="mt-3 space-y-2 text-sm">
                <p>
                  <span className="text-slate-500">Cause:</span>{" "}
                  <span className="text-slate-400">{bug.cause}</span>
                </p>
                <p>
                  <span className="text-emerald-light">Fix:</span>{" "}
                  <span className="text-slate-400">{bug.fix}</span>
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Before/after comparison */}
        <div className="mt-12 grid md:grid-cols-2 gap-6">
          <div className="glass rounded-2xl p-8 text-center border-t-4 border-t-rose">
            <div className="text-4xl font-bold text-rose">0%</div>
            <div className="text-sm text-slate-400 mt-2">
              SI reported before fix
            </div>
            <div className="text-xs text-slate-500 mt-1">
              (Every patient appears perfectly healthy)
            </div>
          </div>
          <div className="glass rounded-2xl p-8 text-center border-t-4 border-t-emerald">
            <div className="text-4xl font-bold text-emerald">17-24%</div>
            <div className="text-sm text-slate-400 mt-2">
              SI correctly detected after fix
            </div>
            <div className="text-xs text-slate-500 mt-1">
              (Pathological walker with 25% true SI)
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
