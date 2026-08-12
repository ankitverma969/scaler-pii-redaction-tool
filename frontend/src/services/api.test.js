import { describe, expect, it } from "vitest";

import { filenameFromContentDisposition } from "./api";

describe("api helpers", () => {
  it("parses and sanitizes download filenames", () => {
    expect(
      filenameFromContentDisposition('attachment; filename="safe_Redacted.docx"'),
    ).toBe("safe_Redacted.docx");
    expect(
      filenameFromContentDisposition(
        "attachment; filename*=UTF-8''unsafe%5Cname_Redacted.docx",
      ),
    ).toBe("unsafe_name_Redacted.docx");
  });

  it("falls back when filename is absent or not a DOCX", () => {
    expect(filenameFromContentDisposition(null)).toBe("redacted_document.docx");
    expect(filenameFromContentDisposition('attachment; filename="report.pdf"')).toBe(
      "redacted_document.docx",
    );
  });
});
