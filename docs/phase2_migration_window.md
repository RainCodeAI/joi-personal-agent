# Phase 2 Migration Window

This document defines how Sprint 2.3 should run in practice.

## Intent

Keep both clients available for a short overlap while validating that the FastAPI backend is complete enough for the Next.js shell to replace Streamlit on core flows.

## Primary Path

- Backend: `uvicorn app.api.main:app --reload`
- Frontend: `cd frontend && npm run dev`
- Public local UI: `http://localhost:3000`

This is the path that should receive feature work, bug fixes for the web UX, and packaging attention.

## Temporary Internal Path

- Internal comparison client: `streamlit run app/ui/app.py`
- Internal local UI: `http://localhost:8501`

This path exists only to compare behavior, verify parity, and keep a fallback client during the overlap.

## Ground Rules

- Do not add new product-facing features only to Streamlit.
- Do not move the default runtime back to Streamlit.
- Keep both clients pointed at the same FastAPI backend whenever possible.
- Treat missing API coverage as backend work, not as a reason to rebuild business logic in the frontend.

## Exit Criteria

Sprint 2.3 is complete when:

1. Next.js is the default documented and packaged web client.
2. Core flows are validated on the Next.js shell against `/api/v2/*`.
3. Streamlit is no longer the default local or container entrypoint.
4. Streamlit remains only as an explicitly temporary internal fallback, or is removed entirely if parity is confirmed.

## Remaining Risks

- The Python test environment is currently inconsistent, which limits clean backend verification.
- Tray and voice flows still lean on legacy components and should be treated as migration follow-up work, not proof that Streamlit must remain primary.
