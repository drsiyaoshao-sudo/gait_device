export default function SectionHeading({
  tag,
  title,
  subtitle,
}: {
  tag: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="text-center mb-16">
      <span className="inline-block rounded-full bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent-light tracking-wide uppercase mb-4">
        {tag}
      </span>
      <h2 className="text-3xl md:text-4xl font-bold text-white">{title}</h2>
      {subtitle && (
        <p className="mt-4 max-w-2xl mx-auto text-lg text-slate-400">
          {subtitle}
        </p>
      )}
    </div>
  );
}
