export default function Section({
  id,
  title,
  description,
  aside,
  className = "",
  children,
}) {
  const headingId = `${id}-heading`;

  return (
    <section
      id={id}
      className={`section ${className}`}
      aria-labelledby={headingId}
    >
      <header className="section__header">
        <div>
          <h2 id={headingId}>{title}</h2>

          {description && (
            <p className="section__description">
              {description}
            </p>
          )}
        </div>

        {aside && (
          <div className="section__aside">
            {aside}
          </div>
        )}
      </header>

      {children}
    </section>
  );
}
