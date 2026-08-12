const STATE_COPY = {
  QUEUED: {
    title: "Queued for processing",
    body: "Your document has been accepted and will begin processing shortly.",
  },
  PROCESSING: {
    title: "Redacting document...",
    body: "We're detecting PII, generating synthetic replacements, and preserving the DOCX structure.",
  },
};

function ProcessingState({ status, filename }) {
  if (!["QUEUED", "PROCESSING"].includes(status)) {
    return null;
  }

  const copy = STATE_COPY[status];

  return (
    <section className="processing-card" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <div>
        <p className="state-label">{status === "QUEUED" ? "Queued" : "Processing"}</p>
        <h2>{copy.title}</h2>
        <p>{copy.body}</p>
        <p className="muted">
          {filename ? `${filename} is being processed. ` : ""}
          Large documents may take a minute or two. You can keep this tab open.
        </p>
      </div>
    </section>
  );
}

export default ProcessingState;
