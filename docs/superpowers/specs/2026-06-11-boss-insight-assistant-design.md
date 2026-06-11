# Boss Insight Assistant Design

## Goal

Build a Windows desktop utility that reads key information from the Boss Zhipin desktop client, summarizes unread conversations, and suggests replies. The tool must let the user configure model names and API keys in the UI, use local extraction first, and fall back to an Aliyun Bailian vision model when local extraction confidence is low.

## Scope

The first release includes:

- Manual scan and background monitoring modes.
- Boss desktop window discovery.
- Local extraction through Windows UI Automation, screenshots, and OCR.
- Vision fallback for low-confidence regions.
- Text-model analysis for unread summaries, prioritization, and reply suggestions.
- A desktop GUI for configuration, monitoring, and results.

The first release does not include:

- Automatic message sending.
- Database persistence.
- Multi-platform support beyond Windows.

## User Experience

The user opens the tool, enters:

- Text model name
- Vision model name
- API key
- Optional base URL

Then the user can:

- Connect to the Boss window
- Click `立即扫描`
- Start or stop monitoring
- Review extracted unread conversations
- Review current chat messages
- Copy suggested replies

## Architecture

The app is a Python desktop application with a Tkinter GUI and service-oriented internals:

1. `gui`
   - Main window
   - Settings form
   - Status and logs
   - Result panes

2. `capture`
   - Boss window discovery
   - UI Automation text collection
   - Window screenshot capture
   - Region segmentation

3. `extraction`
   - Local OCR
   - OCR parsing into structured conversations and messages
   - Confidence scoring
   - Vision fallback orchestration

4. `analysis`
   - Prompt building
   - Bailian text model calls
   - Parsing structured analysis results

5. `monitoring`
   - Polling loop
   - Background thread coordination
   - UI-safe event callbacks

## Data Model

Each scan produces a single `ScanSnapshot`:

- `window`
  - title
  - found
  - bounds
  - captured_at
- `conversation_list`
  - name
  - job_title
  - last_message
  - time_label
  - unread_count
  - selected
  - source
  - confidence
- `current_candidate`
  - name
  - summary lines
  - source
  - confidence
- `current_messages`
  - speaker
  - text
  - time_label
  - source
  - confidence
- `analysis`
  - unread_summary
  - current_chat_summary
  - priorities
  - reply_suggestions
- `diagnostics`
  - fallback_used
  - low_confidence_regions
  - warnings

## Extraction Strategy

The pipeline runs in this order:

1. Find the Boss window.
2. Read visible UI Automation texts when available.
3. Capture a screenshot of the window.
4. Split the screenshot into semantic regions:
   - left navigation
   - conversation list
   - candidate header
   - chat body
5. Run OCR on each region.
6. Parse OCR lines into structured records.
7. Score confidence based on missing required fields, OCR sparsity, and parser quality.
8. If confidence is low for a region, send only that region image to the configured vision model.
9. Merge fallback results into one final snapshot.
10. Send structured text, not the full screenshot, to the configured text model for analysis.

## Vision Fallback Rules

Vision fallback is triggered when any of these conditions hold:

- No conversations are parsed from the conversation list.
- Current chat message count is zero but OCR text exists.
- Required fields such as candidate name or last message are missing.
- OCR output contains too many placeholder or low-information lines.
- A caller explicitly requests fallback for debugging.

Fallback scope is region-based. The whole window is not sent unless region segmentation fails.

## Model Integration

The app uses Aliyun Bailian's OpenAI-compatible endpoints. The UI exposes:

- `base_url`
- `api_key`
- `text_model`
- `vision_model`

Recommended defaults for the first release:

- Text model: `qwen-plus`
- Vision model: `qwen-vl-ocr`
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`

These defaults are recommendations only. The user may override all fields in the GUI.

## Error Handling

- If the Boss window is not found, show a clear status message and keep the app responsive.
- If OCR fails, keep raw text diagnostics in the UI.
- If Bailian requests fail, surface the HTTP error and continue showing local extraction results.
- If monitoring is active and a scan fails, log the failure and retry on the next interval.

## Testing Strategy

The first release focuses automated tests on deterministic logic:

- Settings persistence
- OCR text parsing into structured conversations
- Chat message parsing
- Fallback decision rules
- Prompt/result parsing

Direct UI automation and live OCR accuracy are validated manually.

## Implementation Notes

- Prefer small modules with clear responsibilities.
- Keep the live window integration isolated behind service interfaces so tests can use fake providers.
- Keep all model settings in a local JSON config file under the user's home application directory.
