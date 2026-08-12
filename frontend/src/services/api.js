const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parseError(response) {
  const fallback = `Request failed with status ${response.status}`;
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    return fallback;
  }

  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") {
      return payload.detail;
    }
    if (payload?.detail?.message) {
      return payload.detail.message;
    }
    if (payload?.message) {
      return payload.message;
    }
  } catch {
    return fallback;
  }

  return fallback;
}

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return response.json();
}

export async function checkHealth(options = {}) {
  return requestJson("/api/health", options);
}

export async function createRedactionJob(file, options = {}) {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson("/api/redactions", {
    method: "POST",
    body: formData,
    signal: options.signal,
  });
}

export async function getRedactionJob(jobId, options = {}) {
  return requestJson(`/api/redactions/${encodeURIComponent(jobId)}`, {
    signal: options.signal,
  });
}

export async function deleteRedactionJob(jobId, options = {}) {
  return requestJson(`/api/redactions/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
    signal: options.signal,
  });
}

export async function downloadRedactedDocument(jobId, options = {}) {
  const response = await fetch(
    `${API_BASE_URL}/api/redactions/${encodeURIComponent(jobId)}/download`,
    { signal: options.signal },
  );

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return {
    blob: await response.blob(),
    filename: filenameFromContentDisposition(
      response.headers.get("content-disposition"),
    ),
  };
}

export function filenameFromContentDisposition(value) {
  if (!value) {
    return "redacted_document.docx";
  }

  const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
  const quotedMatch = value.match(/filename="([^"]+)"/i);
  const rawMatch = value.match(/filename=([^;]+)/i);
  const candidate = decodeURIComponent(
    utfMatch?.[1] || quotedMatch?.[1] || rawMatch?.[1] || "",
  )
    .replace(/[\\/:*?"<>|]+/g, "_")
    .trim();

  return candidate.toLowerCase().endsWith(".docx")
    ? candidate
    : "redacted_document.docx";
}
