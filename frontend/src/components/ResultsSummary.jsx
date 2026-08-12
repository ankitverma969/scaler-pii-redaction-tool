import { PII_TYPES } from "../constants/piiTypes";
import { formatDuration } from "../utils/time";

function ResultsSummary({ result, onDownload, isDownloading, downloadError, onReset }) {
  if (!result || result.status !== "COMPLETED") {
    return null;
  }

  const duration = formatDuration(result.processing_seconds);

  return (
    <section className="results-card" aria-labelledby="results-title">
      <div className="results-header">
        <div>
          <p className="state-label success">Complete</p>
          <h2 id="results-title">Redaction Complete</h2>
          <p>
            <strong>{result.total_entities ?? 0}</strong> entities replaced
            {duration ? ` in ${duration}` : ""}.
          </p>
        </div>
      </div>

      <div className="results-grid">
        {PII_TYPES.map((type) => (
          <article className="result-item" key={type.key}>
            <span>{type.label}</span>
            <strong>{Number(result.counts?.[type.key] || 0)}</strong>
          </article>
        ))}
      </div>

      {downloadError ? (
        <p className="download-error" role="alert">
          {downloadError}
        </p>
      ) : null}

      <div className="action-row">
        <button
          className="primary-button"
          type="button"
          onClick={onDownload}
          disabled={isDownloading || !result.download_available}
        >
          {isDownloading ? "Preparing Download..." : "Download Redacted DOCX"}
        </button>
        <button className="secondary-button" type="button" onClick={onReset}>
          Process Another Document
        </button>
      </div>
    </section>
  );
}

export default ResultsSummary;
