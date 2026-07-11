"""Registry-driven execution for validated read and approved write proposals."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.tools.registry import ToolRegistry, tool_registry
from app.tools.types import (
    ApprovedToolExecution,
    ToolExecutionResult,
    ToolProposal,
    ToolVerificationResult,
    fingerprint_tool_arguments,
)


class ToolDispatchError(RuntimeError):
    def __init__(self, message: str, *, code: str = "execution_error") -> None:
        super().__init__(message)
        self.code = code


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or tool_registry
        self._handlers: dict[str, Callable[[dict[str, Any], str], Any]] = {
            "email_summarize_threads": self._email_summarize_threads,
            "send_email": self._send_email,
            "calendar_upcoming": self._calendar_upcoming,
            "create_event": self._create_event,
        }
        self._verifiers: dict[
            str,
            Callable[[dict[str, Any], dict[str, Any], str], ToolVerificationResult],
        ] = {
            "send_email": self._verify_sent_email,
            "create_event": self._verify_created_event,
        }

    def execute(
        self,
        proposal: ToolProposal,
        *,
        approval: ApprovedToolExecution | None = None,
    ) -> ToolExecutionResult:
        spec = self.registry.get(proposal.tool_name)
        if spec is None:
            return self._result(proposal, status="error", error="Unknown tool")
        validation_errors = self.registry.validate_proposal(proposal)
        if validation_errors:
            return self._result(
                proposal,
                status="blocked",
                data={"validation_errors": validation_errors},
                error="Tool arguments failed schema validation",
            )
        if spec.requires_approval:
            approval_error = self._validate_approval(proposal, approval)
            if approval_error:
                return self._result(proposal, status="blocked", error=approval_error)

        handler = self._handlers.get(proposal.tool_name)
        if handler is None:
            return self._result(
                proposal,
                status="error",
                approval=approval,
                error="Tool is registered but execution is not implemented",
            )
        try:
            idempotency_key = proposal.idempotency_key or proposal.proposal_id
            data = handler(dict(proposal.arguments), idempotency_key)
            verification = None
            verifier = self._verifiers.get(proposal.tool_name)
            if verifier is not None:
                verification = verifier(dict(proposal.arguments), data, idempotency_key)
                if not verification.verified:
                    return self._result(
                        proposal,
                        status="error",
                        approval=approval,
                        data=data,
                        error="Provider execution could not be verified",
                        verification=verification,
                    )
            return self._result(
                proposal,
                status="success",
                approval=approval,
                data=data,
                verification=verification,
            )
        except ToolDispatchError as exc:
            return self._result(
                proposal,
                status="error",
                approval=approval,
                data={"code": exc.code},
                error=str(exc),
            )
        except Exception as exc:
            return self._result(
                proposal,
                status="error",
                approval=approval,
                error=str(exc),
            )

    @staticmethod
    def _validate_approval(
        proposal: ToolProposal,
        approval: ApprovedToolExecution | None,
    ) -> str | None:
        if approval is None:
            return "Write execution requires a consumed approval"
        if (
            approval.proposal_id != proposal.proposal_id
            or approval.tool_name != proposal.tool_name
            or approval.operation != proposal.operation
            or approval.arguments != proposal.arguments
        ):
            return "Approved execution does not match proposal"
        actual = fingerprint_tool_arguments(
            proposal_id=proposal.proposal_id,
            tool_name=proposal.tool_name,
            operation=proposal.operation,
            arguments=proposal.arguments,
        )
        if actual != approval.arguments_sha256:
            return "Approved execution fingerprint does not match"
        return None

    @staticmethod
    def _result(
        proposal: ToolProposal,
        *,
        status: str,
        approval: ApprovedToolExecution | None = None,
        data: Any = None,
        error: str = "",
        verification: ToolVerificationResult | None = None,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=proposal.tool_name,
            proposal_id=proposal.proposal_id,
            approval_id=approval.approval_id if approval else None,
            status=status,
            data=data,
            error=error,
            verification=verification,
        )

    @staticmethod
    def _email_summarize_threads(
        args: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        from app.tools import email_gmail

        threads = email_gmail.list_threads(max_results=int(args.get("max_results", 20)))
        return {"summary": email_gmail.summarize_threads(threads)}

    @staticmethod
    def _send_email(args: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        from app.tools import email_gmail

        if not email_gmail.is_authenticated():
            raise ToolDispatchError("Gmail is not authenticated", code="not_authenticated")
        details = email_gmail.send_message(
            to=str(args["to"]).strip(),
            subject=str(args["subject"]).strip(),
            body=str(args["body"]),
            idempotency_key=idempotency_key,
        )
        return {"status": "Email sent", "details": details}

    @staticmethod
    def _calendar_upcoming(
        args: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        from app.tools import calendar_gcal

        if not calendar_gcal.is_authenticated():
            raise ToolDispatchError(
                "Google Calendar is not authenticated",
                code="not_authenticated",
            )
        return {"events": calendar_gcal.upcoming_events(days=int(args.get("days", 1)))}

    @staticmethod
    def _create_event(args: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        from app.tools import calendar_gcal

        if not calendar_gcal.is_authenticated():
            raise ToolDispatchError(
                "Google Calendar is not authenticated",
                code="not_authenticated",
            )
        details = calendar_gcal.create_event(
            summary=str(args["summary"]).strip(),
            start_time=str(args["start_time"]).strip(),
            duration_minutes=int(args.get("duration_minutes", 60)),
            idempotency_key=idempotency_key,
        )
        return {
            "status": "Event created",
            "link": details.get("htmlLink"),
            "details": details,
        }

    @staticmethod
    def _verify_sent_email(
        args: dict[str, Any],
        data: dict[str, Any],
        idempotency_key: str,
    ) -> ToolVerificationResult:
        from app.tools import email_gmail

        details = data.get("details")
        provider_id = details.get("id") if isinstance(details, dict) else None
        if not provider_id:
            return ToolVerificationResult(
                tool_name="send_email",
                status="failed",
                error="Gmail did not return a message ID",
            )
        verification = email_gmail.verify_sent_message(
            str(provider_id),
            idempotency_key,
        )
        verified = bool(verification.get("verified"))
        return ToolVerificationResult(
            tool_name="send_email",
            status="verified" if verified else "failed",
            verified=verified,
            details=verification,
            error="" if verified else "Gmail message read-back did not match",
        )

    @staticmethod
    def _verify_created_event(
        args: dict[str, Any],
        data: dict[str, Any],
        idempotency_key: str,
    ) -> ToolVerificationResult:
        from app.tools import calendar_gcal

        details = data.get("details")
        provider_id = details.get("id") if isinstance(details, dict) else None
        if not provider_id:
            return ToolVerificationResult(
                tool_name="create_event",
                status="failed",
                error="Calendar did not return an event ID",
            )
        verification = calendar_gcal.verify_created_event(
            str(provider_id),
            idempotency_key,
        )
        verified = bool(verification.get("verified"))
        return ToolVerificationResult(
            tool_name="create_event",
            status="verified" if verified else "failed",
            verified=verified,
            details=verification,
            error="" if verified else "Calendar event read-back did not match",
        )


tool_dispatcher = ToolDispatcher()
