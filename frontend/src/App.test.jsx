import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import {
  checkHealth,
  createRedactionJob,
  deleteRedactionJob,
  downloadRedactedDocument,
  getRedactionJob,
} from "./services/api";

vi.mock("./services/api", () => ({
  checkHealth: vi.fn(),
  createRedactionJob: vi.fn(),
  deleteRedactionJob: vi.fn(),
  downloadRedactedDocument: vi.fn(),
  getRedactionJob: vi.fn(),
}));

const completedStatus = {
  job_id: "job-1",
  status: "COMPLETED",
  original_filename: "document.docx",
  processing_seconds: 65.2,
  total_entities: 42,
  download_available: true,
  counts: {
    PERSON: 12,
    EMAIL: 4,
    PHONE: 3,
    COMPANY: 7,
    ADDRESS: 8,
    SSN: 2,
    CREDIT_CARD: 1,
    DOB: 3,
    IP_ADDRESS: 2,
  },
};

function onlineHealth() {
  checkHealth.mockResolvedValue({ status: "ok", service: "pii-redaction-api" });
}

async function renderOnlineApp() {
  onlineHealth();
  render(<App />);
  await screen.findByText("Service online");
}

function docxFile(name = "document.docx", content = "synthetic") {
  return new File([content], name, {
    type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  });
}

async function selectFile(file, options = {}) {
  const input = screen.getByLabelText("DOCX file");
  await userEvent.upload(input, file, options);
}

async function clickButton(name) {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
    await Promise.resolve();
  });
}

async function advanceTimers(ms) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function advanceNextTimer() {
  await act(async () => {
    await vi.advanceTimersToNextTimerAsync();
  });
}

describe("App", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("renders initial state with upload controls and disabled submission", async () => {
    await renderOnlineApp();

    expect(
      screen.getByRole("heading", { name: "PII Redaction Tool" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Upload DOCX")).toBeInTheDocument();
    expect(screen.getByLabelText("DOCX file")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Redact Document" }),
    ).toBeDisabled();
  });

  it("accepts a valid DOCX and enables submission", async () => {
    await renderOnlineApp();
    await selectFile(docxFile("board-pack.docx", "abc".repeat(900)));

    expect(screen.getByText("board-pack.docx")).toBeInTheDocument();
    expect(screen.getByText(/2.6 KB/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Redact Document" }),
    ).toBeEnabled();
  });

  it("rejects invalid, empty, and oversized files client-side", async () => {
    await renderOnlineApp();

    await selectFile(new File(["pdf"], "document.pdf", { type: "application/pdf" }), {
      applyAccept: false,
    });
    expect(screen.getByText("Please select a DOCX file.")).toBeInTheDocument();
    expect(createRedactionJob).not.toHaveBeenCalled();

    await selectFile(new File([], "empty.docx"));
    expect(screen.getByText("The selected DOCX file is empty.")).toBeInTheDocument();

    const oversized = docxFile("large.docx", "small");
    Object.defineProperty(oversized, "size", { value: 11 * 1024 * 1024 });
    await selectFile(oversized);
    expect(
      screen.getByText("The selected file is larger than 10 MB."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Redact Document" }),
    ).toBeDisabled();
  });

  it("creates a job once and shows queued state without exposing the job id", async () => {
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({
      job_id: "opaque-job-id",
      status: "QUEUED",
      status_url: "/api/redactions/opaque-job-id",
    });

    await selectFile(docxFile());
    const submit = screen.getByRole("button", { name: "Redact Document" });
    await userEvent.dblClick(submit);

    await screen.findByText("Queued for processing");
    expect(createRedactionJob).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("opaque-job-id")).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("polls through processing to completion and stops after completion", async () => {
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({
      job_id: "job-1",
      status: "QUEUED",
      status_url: "/api/redactions/job-1",
    });
    getRedactionJob
      .mockResolvedValueOnce({ job_id: "job-1", status: "PROCESSING" })
      .mockResolvedValueOnce(completedStatus);

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    expect(screen.getByText("Queued for processing")).toBeInTheDocument();

    await advanceTimers(2000);
    expect(screen.getByText("Redacting document...")).toBeInTheDocument();
    await advanceTimers(2000);
    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();
    await advanceTimers(6000);

    expect(getRedactionJob).toHaveBeenCalledTimes(2);
  });

  it("renders all nine result categories, total, duration, and no raw mapping", async () => {
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({ job_id: "job-1", status: "PROCESSING" });
    getRedactionJob.mockResolvedValueOnce(completedStatus);

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    await advanceTimers(2000);

    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText(/1 min 5 sec/)).toBeInTheDocument();
    for (const label of [
      "Names",
      "Email Addresses",
      "Phone Numbers",
      "Companies",
      "Addresses",
      "SSNs",
      "Credit Cards",
      "Dates of Birth",
      "IP Addresses",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText(/replacement/i)).not.toBeInTheDocument();
  });

  it("shows safe failure state and reset action", async () => {
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({ job_id: "job-1", status: "PROCESSING" });
    getRedactionJob.mockResolvedValueOnce({
      job_id: "job-1",
      status: "FAILED",
      counts: {},
      download_available: false,
      error: {
        code: "REDACTION_FAILED",
        message: "The document could not be processed.",
      },
    });

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    await advanceTimers(2000);

    expect(screen.getByText("Document processing failed")).toBeInTheDocument();
    expect(screen.queryByText("Redaction Complete")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Choose Another Document" }),
    ).toBeInTheDocument();
  });

  it("handles temporary poll failure without losing the active job", async () => {
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({ job_id: "job-1", status: "PROCESSING" });
    getRedactionJob
      .mockRejectedValueOnce(new Error("temporary network issue"))
      .mockResolvedValueOnce(completedStatus);

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    await advanceTimers(2000);
    expect(screen.getByText("Reconnecting to job status...")).toBeInTheDocument();
    await advanceTimers(2000);

    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();
  });

  it("downloads a completed result without clearing it and reports download failures", async () => {
    global.URL.createObjectURL = vi.fn(() => "blob:download");
    global.URL.revokeObjectURL = vi.fn();
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({ job_id: "job-1", status: "PROCESSING" });
    getRedactionJob.mockResolvedValueOnce(completedStatus);
    downloadRedactedDocument
      .mockResolvedValueOnce({
        blob: new Blob(["docx"]),
        filename: "document_Redacted.docx",
      })
      .mockRejectedValueOnce(new Error("Download failed"));

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    await advanceTimers(2000);
    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();

    await clickButton("Download Redacted DOCX");
    expect(downloadRedactedDocument).toHaveBeenCalledWith("job-1");
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();

    await clickButton("Download Redacted DOCX");
    expect(screen.getByText("Download failed")).toBeInTheDocument();
    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();
  });

  it("resets completed workflow and tolerates delete failure locally", async () => {
    await renderOnlineApp();
    createRedactionJob.mockResolvedValue({ job_id: "job-1", status: "PROCESSING" });
    getRedactionJob.mockResolvedValueOnce(completedStatus);
    deleteRedactionJob.mockRejectedValueOnce(new Error("cleanup failed"));

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    await advanceTimers(2000);
    expect(screen.getByText("Redaction Complete")).toBeInTheDocument();
    await clickButton("Process Another Document");

    expect(deleteRedactionJob).toHaveBeenCalledWith("job-1");
    expect(screen.queryByText("Redaction Complete")).not.toBeInTheDocument();
    expect(screen.getByText("Upload DOCX")).toBeInTheDocument();
    expect(
      screen.getByText("Local workflow was reset, but server cleanup could not be confirmed."),
    ).toBeInTheDocument();
  });

  it("shows offline health state, disables submit, and can retry to online", async () => {
    checkHealth
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ status: "ok" });
    render(<App />);

    expect(await screen.findByText("Backend service unavailable")).toBeInTheDocument();
    await selectFile(docxFile());
    expect(
      screen.getByRole("button", { name: "Redact Document" }),
    ).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Service online")).toBeInTheDocument();
  });

  it("cleans up polling on unmount and ignores late responses", async () => {
    onlineHealth();
    const { unmount } = render(<App />);
    await screen.findByText("Service online");
    createRedactionJob.mockResolvedValue({ job_id: "job-1", status: "PROCESSING" });
    let resolveStatus;
    getRedactionJob.mockReturnValue(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }),
    );

    await selectFile(docxFile());
    vi.useFakeTimers();
    await clickButton("Redact Document");
    await advanceNextTimer();
    expect(getRedactionJob).toHaveBeenCalledTimes(1);
    unmount();
    resolveStatus(completedStatus);
    await advanceTimers(6000);

    expect(getRedactionJob).toHaveBeenCalledTimes(1);
  });
});
