import SectionHeading from "./SectionHeading";

const problems = [
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: "Months of iteration",
    description:
      "A single hardware bug means redesigning PCBs, reordering components, and waiting weeks for new prototypes. Each cycle costs time and money.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
      </svg>
    ),
    title: "Bugs found too late",
    description:
      "Critical firmware defects only surface when the hardware arrives. By then, you've already committed to a design — and the fix requires starting over.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
      </svg>
    ),
    title: "Expensive dead ends",
    description:
      "Each prototype iteration costs $10K–$100K+ in NRE. Teams burn through runway chasing bugs that could have been caught in simulation.",
  },
  {
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
      </svg>
    ),
    title: "Team silos",
    description:
      "Firmware engineers, hardware designers, and algorithm developers work in isolation. Integration happens at the end — when it's most expensive to fix.",
  },
];

export default function Problem() {
  return (
    <section id="problem" className="py-24 relative">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeading
          tag="The Problem"
          title="The hardware-software death spiral"
          subtitle="Hardware teams are stuck in a cycle where every bug discovered after fabrication triggers weeks of rework. Software solved this decades ago with CI/CD. Hardware hasn't — until now."
        />

        <div className="grid md:grid-cols-2 gap-6">
          {problems.map((p) => (
            <div
              key={p.title}
              className="glass rounded-2xl p-8 hover:border-rose/30 transition-colors group"
            >
              <div className="text-rose group-hover:text-rose-light transition-colors">
                {p.icon}
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">
                {p.title}
              </h3>
              <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                {p.description}
              </p>
            </div>
          ))}
        </div>

        {/* Visual separator */}
        <div className="mt-20 flex items-center justify-center">
          <div className="h-px w-20 bg-gradient-to-r from-transparent to-accent/50" />
          <span className="mx-4 text-sm text-accent-light font-medium">
            There&apos;s a better way
          </span>
          <div className="h-px w-20 bg-gradient-to-l from-transparent to-accent/50" />
        </div>
      </div>
    </section>
  );
}
