"""Remote surfaces that route into the existing Joi API (localhost clients).

These integrations never embed the agent pipeline; they are thin clients of the
FastAPI backend so memory, approvals, and behaviour stay centralized.
"""
