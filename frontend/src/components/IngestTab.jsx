import React, { useState } from "react";
import { ingestUrl, uploadPdf } from "../api.js";
import DropZone from "./DropZone.jsx";

export default function IngestTab() {
  const [sourceType, setSourceType] = useState("url");
  const [url, setUrl] = useState("");
  const [crawlMode, setCrawlMode] = useState("single");
  const [urlPattern, setUrlPattern] = useState("");
  const [maxPages, setMaxPages] = useState("");
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfValidation, setPdfValidation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState(null);

  function resetNotice() {
    setNotice(null);
  }

  async function handleUrlSubmit(event) {
    event.preventDefault();
    resetNotice();

    if (!url.trim()) {
      setNotice({ type: "error", text: "Enter a URL to ingest." });
      return;
    }

    const parsedMaxPages = Number.parseInt(maxPages, 10);
    if (
      crawlMode === "crawl" &&
      (!maxPages || Number.isNaN(parsedMaxPages) || parsedMaxPages < 1)
    ) {
      setNotice({
        type: "error",
        text: "Max pages is required for crawl mode. Enter a number between 1 and 500."
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await ingestUrl({
        url: url.trim(),
        crawlMode,
        urlPattern: urlPattern.trim(),
        maxPages: crawlMode === "crawl" ? parsedMaxPages : undefined
      });

      if (response.status === "duplicate") {
        setNotice({ type: "info", text: "Already ingested — skipped" });
      } else {
        setNotice({ type: "success", text: "URL ingestion started." });
      }
    } catch (error) {
      setNotice({
        type: "error",
        text: error.message || "URL ingestion failed."
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePdfSubmit(event) {
    event.preventDefault();
    resetNotice();

    if (!pdfFile) {
      setPdfValidation("Choose a PDF file before uploading.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await uploadPdf(pdfFile);
      if (response.status === "duplicate") {
        setNotice({ type: "info", text: "Already ingested — skipped" });
      } else {
        setNotice({ type: "success", text: "PDF ingestion started." });
      }
    } catch (error) {
      setNotice({
        type: "error",
        text: error.message || "PDF upload failed."
      });
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleFileAccepted(file) {
    setPdfFile(file);
    setPdfValidation("");
    resetNotice();
  }

  function handleFileRejected(message) {
    setPdfFile(null);
    setPdfValidation(message);
    resetNotice();
  }

  return (
    <section className="workspace-panel" aria-labelledby="ingest-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Source</p>
          <h2 id="ingest-title">Ingest documents</h2>
        </div>
        <div className="segmented-control" role="group" aria-label="Source type">
          <button
            type="button"
            className={sourceType === "url" ? "segment active" : "segment"}
            onClick={() => {
              setSourceType("url");
              resetNotice();
            }}
          >
            URL
          </button>
          <button
            type="button"
            className={sourceType === "pdf" ? "segment active" : "segment"}
            onClick={() => {
              setSourceType("pdf");
              resetNotice();
            }}
          >
            PDF
          </button>
        </div>
      </div>

      {sourceType === "url" ? (
        <form className="form-grid" onSubmit={handleUrlSubmit}>
          <label className="field">
            <span>URL</span>
            <input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com/kb/article"
            />
          </label>

          <fieldset className="field-group">
            <legend>Crawl scope</legend>
            <label className="radio-line">
              <input
                type="radio"
                name="crawl-mode"
                value="single"
                checked={crawlMode === "single"}
                onChange={() => setCrawlMode("single")}
              />
              <span>Single page</span>
            </label>
            <label className="radio-line">
              <input
                type="radio"
                name="crawl-mode"
                value="crawl"
                checked={crawlMode === "crawl"}
                onChange={() => setCrawlMode("crawl")}
              />
              <span>Crawl all linked pages</span>
            </label>
          </fieldset>

          {crawlMode === "crawl" && (
            <>
              <label className="field">
                <span>URL pattern filter</span>
                <input
                  type="text"
                  value={urlPattern}
                  onChange={(event) => setUrlPattern(event.target.value)}
                  placeholder="e.g. /kb/networking/*"
                />
              </label>

              <label className="field">
                <span>
                  Max pages to crawl <span style={{ color: "red" }}>*</span>
                </span>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={maxPages}
                  onChange={(event) => setMaxPages(event.target.value)}
                  placeholder="e.g. 20"
                  required
                />
                <small style={{ color: "#888" }}>
                  Limit how many linked pages are ingested (1-500)
                </small>
              </label>
            </>
          )}

          {notice && <p className={`notice ${notice.type}`}>{notice.text}</p>}

          <div className="form-actions">
            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting ? "Ingesting..." : "Ingest URL"}
            </button>
          </div>
        </form>
      ) : (
        <form className="form-grid" onSubmit={handlePdfSubmit}>
          <DropZone
            selectedFile={pdfFile}
            validationMessage={pdfValidation}
            onFileAccepted={handleFileAccepted}
            onFileRejected={handleFileRejected}
          />

          {notice && <p className={`notice ${notice.type}`}>{notice.text}</p>}

          <div className="form-actions">
            <button type="submit" className="primary-button" disabled={isSubmitting}>
              {isSubmitting ? "Uploading..." : "Upload PDF"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
