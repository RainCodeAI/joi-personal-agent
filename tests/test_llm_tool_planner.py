from app.orchestrator.agents.executor import ExecutorAgent
from app.orchestrator.agents.tool_planner import LLMToolPlanner


def _route(response: str, model: str = "test"):
    return lambda _prompt, _context: {
        "response": response,
        "model_used": model,
        "errors": [],
        "route": [model],
    }


def test_planner_emits_registry_bound_write_proposal():
    planner = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"send_email","arguments":'
        '{"to":"rain@example.com","subject":"Hi","body":"Hello"},'
        '"rationale":"The user asked to send it."}]}'
    ))

    plan = planner.plan("Send an email")

    assert plan.valid is True
    assert plan.proposals[0].operation.value == "write"
    assert plan.proposals[0].idempotency_key == plan.proposals[0].proposal_id


def test_planner_marks_missing_required_values_as_needs_input():
    planner = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"create_event","arguments":'
        '{"summary":"Lunch"}}]}'
    ))

    proposal = planner.plan("Schedule lunch").proposals[0]

    assert proposal.status == "needs_input"
    assert proposal.missing_fields == ["start_time"]


def test_planner_rejects_unknown_tools_fields_and_invalid_argument_types():
    unknown = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"shell","arguments":{}}]}'
    )).plan("Run shell")
    extra = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"calendar_upcoming","arguments":{},"x":1}]}'
    )).plan("Check calendar")
    invalid_type = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"calendar_upcoming",'
        '"arguments":{"days":"tomorrow"}}]}'
    )).plan("Check calendar")

    assert unknown.valid is False
    assert extra.valid is False
    assert invalid_type.valid is False


def test_planner_accepts_empty_plan_and_rejects_malformed_json():
    assert LLMToolPlanner(route_fn=_route('{"proposals":[]}')).plan("Hi").valid
    assert not LLMToolPlanner(route_fn=_route("not json")).plan("Check email").valid


def test_executor_preserves_planned_write_identity_until_approval():
    planner = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"send_email","arguments":'
        '{"to":"rain@example.com","subject":"Hi","body":"Hello"}}]}'
    ))
    proposal = planner.plan("Send email").proposals[0]

    call = ExecutorAgent().execute_proposals([proposal])[0]

    assert call.status == "pending"
    assert call.proposal_id == proposal.proposal_id
    assert call.idempotency_key == proposal.idempotency_key


def test_executor_executes_validated_read(monkeypatch):
    planner = LLMToolPlanner(route_fn=_route(
        '{"proposals":[{"tool_name":"calendar_upcoming",'
        '"arguments":{"days":2}}]}'
    ))
    proposal = planner.plan("Check calendar").proposals[0]
    monkeypatch.setattr("app.tools.calendar_gcal.is_authenticated", lambda: True)
    monkeypatch.setattr(
        "app.tools.calendar_gcal.upcoming_events",
        lambda days: [{"summary": "Lunch", "days": days}],
    )

    call = ExecutorAgent().execute_proposals([proposal])[0]

    assert call.status == "success"
    assert call.result["events"][0]["days"] == 2
    assert call.proposal_id == proposal.proposal_id
