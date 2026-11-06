export function Toast({ message }: { message: string }) {
  return (
    <div className={`toast ${message ? 'is-visible' : ''}`} role="status" aria-live="polite">
      <span className="status-dot" aria-hidden="true" />
      {message}
    </div>
  );
}
