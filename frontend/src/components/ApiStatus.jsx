const STATUS_LABELS = {
  checking: "Checking service",
  online: "Service online",
  offline: "Backend service unavailable",
};

function ApiStatus({ status, onRetry, isChecking }) {
  const isOffline = status === "offline";

  return (
    <section
      className={`api-status ${status}`}
      aria-live="polite"
      aria-label="Backend service status"
    >
      <span className="status-dot" aria-hidden="true" />
      <span>{STATUS_LABELS[status] || STATUS_LABELS.checking}</span>
      {isOffline ? (
        <button
          className="text-button"
          type="button"
          onClick={onRetry}
          disabled={isChecking}
        >
          Retry
        </button>
      ) : null}
    </section>
  );
}

export default ApiStatus;
