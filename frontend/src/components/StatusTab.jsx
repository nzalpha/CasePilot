import React, { useEffect, useMemo, useState } from "react";
import { deleteDocument, fetchDocuments } from "../api.js";
import StatusBadge from "./StatusBadge.jsx";

function formatTimestamp(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function chunkCount(value) {
  return value ? value : "—";
}

function TypeBadge({ type }) {
  const label = type === "pdf" ? "PDF" : "URL";
  return <span className={`type-badge ${type}`}>{label}</span>;
}

export default function StatusTab() {
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState("");
  const [deletingDocumentId, setDeletingDocumentId] = useState("");
  const [deleteErrors, setDeleteErrors] = useState({});

  async function loadDocuments() {
    setIsLoading(true);
    setError("");
    try {
      const records = await fetchDocuments();
      setDocuments(Array.isArray(records) ? records : []);
      setLastUpdated(new Date());
    } catch (loadError) {
      setError(loadError.message || "Unable to fetch documents.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  const hasProcessing = documents.some(
    (document) => document.status === "processing"
  );

  useEffect(() => {
    if (!hasProcessing) {
      return undefined;
    }

    const intervalId = window.setInterval(loadDocuments, 10000);
    return () => window.clearInterval(intervalId);
  }, [hasProcessing]);

  const stats = useMemo(() => {
    return documents.reduce(
      (totals, document) => {
        totals.total += 1;
        if (document.status === "completed") totals.completed += 1;
        if (document.status === "processing") totals.processing += 1;
        if (document.status === "failed") totals.failed += 1;
        return totals;
      },
      { total: 0, completed: 0, processing: 0, failed: 0 }
    );
  }, [documents]);

  function startDeleteConfirmation(documentId) {
    setConfirmingDeleteId(documentId);
    setDeleteErrors((currentErrors) => ({
      ...currentErrors,
      [documentId]: ""
    }));
  }

  function cancelDeleteConfirmation(documentId) {
    setConfirmingDeleteId((currentId) =>
      currentId === documentId ? "" : currentId
    );
  }

  async function confirmDelete(documentId) {
    setDeletingDocumentId(documentId);
    setDeleteErrors((currentErrors) => ({
      ...currentErrors,
      [documentId]: ""
    }));

    try {
      await deleteDocument(documentId);
      setDocuments((currentDocuments) =>
        currentDocuments.filter((document) => document.document_id !== documentId)
      );
      setConfirmingDeleteId("");
    } catch (deleteError) {
      setDeleteErrors((currentErrors) => ({
        ...currentErrors,
        [documentId]: "Delete failed — try again"
      }));
      setConfirmingDeleteId("");
    } finally {
      setDeletingDocumentId("");
    }
  }

  return (
    <section className="workspace-panel" aria-labelledby="status-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Documents</p>
          <h2 id="status-title">Ingestion status</h2>
        </div>
        <button
          type="button"
          className="secondary-button"
          onClick={loadDocuments}
          disabled={isLoading}
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="stats-bar" aria-label="Document totals">
        <div className="stat">
          <span>Total</span>
          <strong>{stats.total}</strong>
        </div>
        <div className="stat completed">
          <span>Completed</span>
          <strong>{stats.completed}</strong>
        </div>
        <div className="stat processing">
          <span>Processing</span>
          <strong>{stats.processing}</strong>
        </div>
        <div className="stat failed">
          <span>Failed</span>
          <strong>{stats.failed}</strong>
        </div>
      </div>

      {error && <p className="notice error">{error}</p>}
      {lastUpdated && (
        <p className="last-updated">Updated {formatTimestamp(lastUpdated)}</p>
      )}

      <div className="table-wrap">
        <table className="documents-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Source</th>
              <th>Status</th>
              <th>Timestamp</th>
              <th>Chunks</th>
              <th className="actions-heading">Action</th>
            </tr>
          </thead>
          <tbody>
            {documents.length === 0 ? (
              <tr>
                <td colSpan="6" className="empty-state">
                  No documents found.
                </td>
              </tr>
            ) : (
              documents.map((document) => {
                const documentId = document.document_id || document.source;
                const isProcessing = document.status === "processing";
                const isConfirming = confirmingDeleteId === documentId;
                const isDeleting = deletingDocumentId === documentId;
                const deleteError = deleteErrors[documentId];

                return (
                  <tr key={documentId}>
                    <td data-label="Type">
                      <TypeBadge type={document.source_type} />
                    </td>
                    <td data-label="Source" className="source-cell">
                      <span>{document.source}</span>
                      {document.source_type === "url" && document.crawl_mode && (
                        <small>
                          {document.crawl_mode === "crawl" ? "Crawl" : "Single"}
                          {document.url_pattern
                            ? ` · pattern: ${document.url_pattern}`
                            : ""}
                        </small>
                      )}
                    </td>
                    <td data-label="Status">
                      <StatusBadge status={document.status} />
                    </td>
                    <td data-label="Timestamp">
                      {formatTimestamp(document.uploaded_at)}
                    </td>
                    <td data-label="Chunks">{chunkCount(document.chunk_count)}</td>
                    <td data-label="Action" className="actions-cell">
                      {isDeleting ? (
                        <span className="inline-status">Deleting...</span>
                      ) : isConfirming ? (
                        <div className="delete-confirmation">
                          <button
                            type="button"
                            className="confirm-delete-button"
                            onClick={() => confirmDelete(documentId)}
                            disabled={isDeleting}
                          >
                            Confirm delete
                          </button>
                          <button
                            type="button"
                            className="cancel-delete-button"
                            onClick={() => cancelDeleteConfirmation(documentId)}
                            disabled={isDeleting}
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="delete-button"
                            onClick={() => startDeleteConfirmation(documentId)}
                            disabled={isProcessing}
                            title={
                              isProcessing
                                ? "Cannot delete while processing"
                                : "Delete document"
                            }
                          >
                            Delete
                          </button>
                          {isProcessing && (
                            <small className="delete-note">
                              Cannot delete while processing
                            </small>
                          )}
                        </>
                      )}
                      {deleteError && (
                        <small className="delete-error">{deleteError}</small>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
