export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-midnight">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <span className="text-xl font-bold gradient-text">Crucible</span>
            <p className="mt-2 text-sm text-slate-500">
              Hardware development at the speed of software.
            </p>
          </div>
          <div className="flex gap-8 text-sm text-slate-500">
            <a href="#problem" className="hover:text-white transition-colors">
              Problem
            </a>
            <a href="#solution" className="hover:text-white transition-colors">
              Solution
            </a>
            <a
              href="#how-it-works"
              className="hover:text-white transition-colors"
            >
              How It Works
            </a>
            <a
              href="#case-study"
              className="hover:text-white transition-colors"
            >
              Case Study
            </a>
          </div>
        </div>
        <div className="mt-8 pt-8 border-t border-white/5 text-center text-xs text-slate-500">
          &copy; {new Date().getFullYear()} Crucible. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
