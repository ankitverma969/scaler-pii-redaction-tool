export const MAX_UPLOAD_SIZE_MB = 10;
export const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

export function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 bytes";
  }

  const units = ["bytes", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  if (unitIndex === 0) {
    return `${size} ${units[unitIndex]}`;
  }

  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function validateDocxFile(file) {
  if (!file) {
    return "Please select a DOCX file.";
  }

  if (!file.name || !file.name.toLowerCase().endsWith(".docx")) {
    return "Please select a DOCX file.";
  }

  if (file.size <= 0) {
    return "The selected DOCX file is empty.";
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return `The selected file is larger than ${MAX_UPLOAD_SIZE_MB} MB.`;
  }

  return "";
}
