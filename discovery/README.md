# WorkFlowOS - Discovery Module (Phase 2+)

## Overview
The **Discovery** module analyzes recorded user activity events to identify recurring routines and candidate workflows suitable for automation.

## Future Pipeline Stage: `DETECT REPETITION`
- **Pattern Mining**: Frequency analysis and sequence mining across application events (e.g., repeated sequences such as `open_email -> download_attachment -> search_customer -> update_customer`).
- **Session Segmentation**: Grouping continuous event streams into logical task episodes based on temporal gaps and context transitions.
- **Repetition Scoring**: Ranking workflow candidates by repetition frequency, potential time saved, and structural determinism.

> **Note**: In Phase 1, raw events are ingested and indexed in MongoDB for subsequent pattern discovery.
