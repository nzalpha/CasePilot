async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null
        ? payload.detail || payload.message
        : payload;
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return payload;
}

export async function ingestUrl({ url, crawlMode, urlPattern }) {
  const payload = {
    url,
    crawl_mode: crawlMode,
    ...(crawlMode === "crawl" && urlPattern ? { url_pattern: urlPattern } : {})
  };

  const response = await fetch("/ingest-url", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  return parseResponse(response);
}

export async function uploadPdf(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/upload-pdf", {
    method: "POST",
    body: formData
  });

  return parseResponse(response);
}

export async function fetchDocuments() {
  const response = await fetch("/documents");
  return parseResponse(response);
}

export async function deleteDocument(documentId) {
  const response = await fetch(`/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE"
  });

  return parseResponse(response);
}
