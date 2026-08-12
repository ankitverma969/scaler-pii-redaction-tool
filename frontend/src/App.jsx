import { useCallback, useEffect, useRef, useState } from "react";

import "./App.css";
import ApiStatus from "./components/ApiStatus";
import ErrorMessage from "./components/ErrorMessage";
import Header from "./components/Header";
import ProcessingState from "./components/ProcessingState";
import ResultsSummary from "./components/ResultsSummary";
import SelectedFile from "./components/SelectedFile";
import UploadZone from "./components/UploadZone";
import {
  checkHealth,
  createRedactionJob,
  deleteRedactionJob,
  downloadRedactedDocument,
  getRedactionJob,
} from "./services/api";
import { validateDocxFile } from "./utils/file";

const ACTIVE_STATUSES = new Set(["QUEUED", "PROCESSING"]);

function App() {
  const [apiStatus, setApiStatus] = useState("checking");
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileError, setFileError] = useState("");
  const [appError, setAppError] = useState("");
  const [jobId, setJobId] = useState("");
  const [jobStatus, setJobStatus] = useState("");
  const [result, setResult] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [pollFailures, setPollFailures] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const jobIdRef = useRef("");

  const isActiveJob = ACTIVE_STATUSES.has(jobStatus);
  const isBusy = isUploading || isActiveJob;
  const canSubmit =
    selectedFile && !fileError && !isBusy && apiStatus === "online";

  const refreshHealth = useCallback(async () => {
    const controller = new AbortController();
    setIsCheckingHealth(true);
    try {
      const health = await checkHealth({ signal: controller.signal });
      setApiStatus(health.status === "ok" ? "online" : "offline");
    } catch {
      setApiStatus("offline");
    } finally {
      setIsCheckingHealth(false);
    }
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setIsCheckingHealth(true);

    checkHealth({ signal: controller.signal })
      .then((health) => {
        setApiStatus(health.status === "ok" ? "online" : "offline");
      })
      .catch(() => setApiStatus("offline"))
      .finally(() => setIsCheckingHealth(false));

    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    jobIdRef.current = jobId;
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !ACTIVE_STATUSES.has(jobStatus)) {
      return undefined;
    }

    const controller = new AbortController();
    const intervalId = window.setInterval(async () => {
      try {
        const status = await getRedactionJob(jobId, {
          signal: controller.signal,
        });
        if (jobIdRef.current !== jobId) {
          return;
        }
        setJobStatus(status.status);
        setPollFailures(0);
        if (status.status === "COMPLETED") {
          setResult(status);
          setAppError("");
        }
        if (status.status === "FAILED") {
          setResult(status);
          setAppError(
            status.error?.message || "The document could not be processed.",
          );
        }
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setPollFailures((current) => {
          const next = current + 1;
          if (next >= 3) {
            setAppError(
              error.message ||
                "Unable to refresh job status. Please check the backend service.",
            );
          }
          return next;
        });
      }
    }, 2000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [jobId, jobStatus]);

  function handleFileSelected(file) {
    const error = validateDocxFile(file);
    setSelectedFile(error ? null : file);
    setFileError(error);
    setAppError("");
    setDownloadError("");
  }

  function removeFile() {
    setSelectedFile(null);
    setFileError("");
  }

  async function submitRedaction(event) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    setIsUploading(true);
    setAppError("");
    setDownloadError("");
    setResult(null);

    try {
      const accepted = await createRedactionJob(selectedFile);
      setJobId(accepted.job_id);
      setJobStatus(accepted.status);
    } catch (error) {
      setAppError(error.message || "Unable to create redaction job.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDownload() {
    if (!jobId) {
      return;
    }

    setIsDownloading(true);
    setDownloadError("");
    try {
      const { blob, filename } = await downloadRedactedDocument(jobId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename || "redacted_document.docx";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      setDownloadError(error.message || "Download failed. Please try again.");
    } finally {
      setIsDownloading(false);
    }
  }

  async function resetWorkflow() {
    const idToDelete = jobId;
    setSelectedFile(null);
    setFileError("");
    setAppError("");
    setDownloadError("");
    setResult(null);
    setJobId("");
    setJobStatus("");
    setPollFailures(0);

    if (idToDelete && ["COMPLETED", "FAILED"].includes(jobStatus)) {
      try {
        await deleteRedactionJob(idToDelete);
      } catch {
        setAppError(
          "Local workflow was reset, but server cleanup could not be confirmed.",
        );
      }
    }
  }

  return (
    <main className="app-shell">
      <div className="app-container">
        <Header />
        <ApiStatus
          status={apiStatus}
          onRetry={refreshHealth}
          isChecking={isCheckingHealth}
        />

        <form className="workflow-card" onSubmit={submitRedaction}>
          <UploadZone disabled={isBusy} onFileSelected={handleFileSelected} />
          <SelectedFile
            file={selectedFile}
            disabled={isBusy}
            onRemove={removeFile}
          />
          <ErrorMessage message={fileError || appError} />
          {pollFailures > 0 && pollFailures < 3 ? (
            <p className="connection-warning" role="status">
              Reconnecting to job status...
            </p>
          ) : null}
          <div className="action-row">
            <button
              className="primary-button"
              type="submit"
              disabled={!canSubmit}
            >
              {isUploading
                ? "Uploading..."
                : isActiveJob
                  ? "Processing..."
                  : "Redact Document"}
            </button>
          </div>
        </form>

        <ProcessingState status={jobStatus} filename={selectedFile?.name} />

        {jobStatus === "FAILED" ? (
          <section className="failure-card" aria-live="polite">
            <p className="state-label danger">Failed</p>
            <h2>Document processing failed</h2>
            <p>{result?.error?.message || "The document could not be processed."}</p>
            <button className="secondary-button" type="button" onClick={resetWorkflow}>
              Choose Another Document
            </button>
          </section>
        ) : null}

        <ResultsSummary
          result={result}
          onDownload={handleDownload}
          isDownloading={isDownloading}
          downloadError={downloadError}
          onReset={resetWorkflow}
        />

        <section className="info-strip" aria-label="Privacy and supported formats">
          <p>
            DOCX only. Supports names, emails, phone numbers, companies,
            addresses, SSNs, credit cards, dates of birth, and IP addresses.
          </p>
          <p>
            Uploaded documents are processed temporarily; the source upload is
            removed after processing and the output remains temporarily available
            for download.
          </p>
        </section>
      </div>
    </main>
  );
}

export default App;
