from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .ai_schemas import Reason, Risk, Route, Triage
from .knowledge import KnowledgeBase, Passage
from .providers import ProviderError, SupportProvider, detect_risks


@dataclass(frozen=True)
class Outcome:
    triage: Triage | None
    risk_flags: list[Risk]
    route: Route
    reason: Reason | None
    draft: str | None
    sources: list[Passage]


class WorkflowState(TypedDict, total=False):
    subject: str
    description: str
    triage: Triage | None
    risk_flags: list[Risk]
    reason: Reason | None
    passages: list[Passage]
    outcome: Outcome


class SupportWorkflow:
    def __init__(self, provider: SupportProvider, knowledge: KnowledgeBase):
        self.provider = provider
        self.knowledge = knowledge

        graph = StateGraph(WorkflowState)  # ty: ignore[invalid-argument-type]
        graph.add_node("classify", self.classify)
        graph.add_node("retrieve", self.retrieve)
        graph.add_node("draft", self.draft)
        graph.add_node("review", self.review)
        graph.add_edge(START, "classify")
        graph.add_conditional_edges(
            "classify", self.next_step, {"continue": "retrieve", "review": "review"}
        )
        graph.add_conditional_edges(
            "retrieve", self.next_step, {"continue": "draft", "review": "review"}
        )
        graph.add_conditional_edges(
            "draft", self.next_step, {"continue": END, "review": "review"}
        )
        graph.add_edge("review", END)
        self.graph = graph.compile()

    def run(self, subject: str, description: str) -> Outcome:
        return self.graph.invoke({"subject": subject, "description": description})[
            "outcome"
        ]

    def classify(self, state: WorkflowState) -> dict:
        known_risks = detect_risks(f"{state['subject']} {state['description']}")
        try:
            triage = self.provider.classify(state["subject"], state["description"])
        except ProviderError:
            return {"triage": None, "risk_flags": known_risks, "reason": "model_error"}
        risk_flags = list(dict.fromkeys([*known_risks, *triage.risk_flags]))
        return {
            "triage": triage,
            "risk_flags": risk_flags,
            "reason": "risk" if risk_flags else None,
        }

    def retrieve(self, state: WorkflowState) -> dict:
        passages = self.knowledge.search(f"{state['subject']} {state['description']}")
        return {"passages": passages, "reason": None if passages else "no_evidence"}

    def draft(self, state: WorkflowState) -> dict:
        passages = state["passages"]
        try:
            proposal = self.provider.draft(
                state["subject"], state["description"], passages
            )
        except ProviderError:
            return {"reason": "model_error"}
        by_id = {passage.passage_id: passage for passage in passages}
        if not proposal.reply or any(
            source_id not in by_id for source_id in proposal.source_ids
        ):
            return {"reason": "insufficient_evidence"}
        return {
            "outcome": Outcome(
                state["triage"],
                state["risk_flags"],
                "draft_ready",
                None,
                proposal.reply,
                [by_id[source_id] for source_id in proposal.source_ids],
            )
        }

    @staticmethod
    def next_step(state: WorkflowState) -> str:
        return "review" if state["reason"] else "continue"

    @staticmethod
    def review(state: WorkflowState) -> dict:
        return {
            "outcome": Outcome(
                state["triage"],
                state["risk_flags"],
                "human_review",
                state["reason"],
                None,
                [],
            )
        }
