export function BrowseSkeleton() {
  return (
    <>
      <div className="skeleton-grid four-col top-gap">
        {Array.from({ length: 8 }).map((_, i) => (
          <article key={i} className="skeleton-card">
            <div className="skeleton-photo" />
            <div className="skeleton-content">
              <div className="skeleton-line skeleton-title" />
              <div className="skeleton-line skeleton-category" />
              <div className="skeleton-line skeleton-price" />
              <div className="skeleton-line skeleton-button" />
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
