# CasePilot Frontend

## 1. What This Frontend Does

This frontend is the web interface for CasePilot. It lets users upload PDFs or ingest URLs into the CasePilot knowledge base. It also lets users watch the status of every ingestion so they can see whether each document is still processing, completed, failed, or skipped as a duplicate.

## 2. What Each File Does

### Pages/Tabs

- `src/App.jsx` starts the React app (the browser code) and switches between the Ingest tab and the Status tab.
- `src/components/IngestTab.jsx` shows the URL form and PDF upload form, then sends the selected source to the backend.
- `src/components/StatusTab.jsx` shows the document list, status counts, refresh button, and automatic refresh behavior.
- `src/styles.css` controls how the whole app looks, including layout, buttons, badges, tables, and mobile screens.

### Components

- `src/components/DropZone.jsx` shows the PDF drag-and-drop area and checks that the selected file ends in `.pdf`.
- `src/components/StatusBadge.jsx` shows a colored label for each document status.

### api.js

- `src/api.js` contains all API calls (requests from the browser to the backend) for uploading PDFs, ingesting URLs, and fetching documents.

## 3. How The Two Tabs Work

### Ingest Tab

- The Ingest tab starts with URL selected.
- The URL form has a URL input and a crawl scope choice.
- `Single page` sends only the URL you entered.
- `Crawl all linked pages` asks the backend to find links on the page and ingest them too.
- The URL pattern filter is optional and only appears for crawl mode.
- When you submit the URL form, the frontend sends the URL, crawl mode, and optional pattern to `/ingest-url`.
- The PDF form has a drag-and-drop area that also opens a file picker when clicked.
- The PDF form accepts only `.pdf` files and shows a message if another file type is selected.
- When you submit the PDF form, the frontend sends the file to `/upload-pdf`.

### Status Tab

- The Status tab fetches the document list from `/documents`.
- Each document shows its type, source, status, upload time, and chunk count.
- A PDF type badge and URL type badge use different colors.
- A green status badge means ingestion completed.
- A blue pulsing status badge means ingestion is still processing.
- A red status badge means something failed.
- An orange status badge means the document was already ingested and skipped.
- The stats header shows total, completed, processing, and failed counts.
- The Refresh button fetches the latest document list.
- If any document is processing, the tab refreshes itself every 10 seconds.

## 4. How The Frontend Talks To The Backend

An API call is a request from the browser to the backend asking it to do something or return data. This frontend sends API calls when a user uploads a PDF, ingests a URL, or opens the Status tab. During development, Vite (the frontend development server) proxies requests to `http://localhost:8000`, which means the browser can talk to the backend without CORS (a browser safety rule that can block requests between different addresses) problems. All API calls live in `src/api.js`.

## 5. What The Status Values Mean

| Status | Colour | Meaning |
|---|---|---|
| completed | green | ingestion finished successfully |
| processing | blue | ingestion is still running |
| failed | red | something went wrong |
| duplicate | orange | already ingested, skipped |

## SUMMARY

The user opens the CasePilot frontend in the browser.
They choose the Ingest tab.
They submit either a URL or a PDF.
The frontend sends that request to the backend.
The user opens the Status tab to watch progress.
The Status tab refreshes while documents are processing.
The document appears as `completed` when ingestion finishes.

## HOW TO RUN

1. Install Node.js (a tool that runs JavaScript projects) if it is not already installed.

   Go to this website and install the recommended version:

   ```text
   https://nodejs.org/
   ```

2. Run `npm install`. npm is the command that installs JavaScript packages.

   ```bash
   cd /Users/nawaz/Desktop/Vibe/WebApp/frontend
   npm install
   ```

3. Run `npm run dev`.

   ```bash
   npm run dev
   ```

4. Open the browser at the URL shown in the terminal.

   It is usually:

   ```text
   http://localhost:5173
   ```

5. Make sure the backend is also running.

   Read the backend guide here:

   ```text
   ../backend/README.md
   ```
