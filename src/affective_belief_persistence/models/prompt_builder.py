"""Versioned, privacy-bounded prompt construction."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field

from affective_belief_persistence.determinism import canonical_json, sha256_value
from affective_belief_persistence.models.contracts import (
    ActionOutput,
    ModelInput,
    PublicLanguageOutput,
    RunnerModel,
)


class PromptError(ValueError):
    """A prompt bundle is absent, drifted, or asks for private reasoning."""


class RenderedPrompt(RunnerModel):
    version: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    text: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


_PRIVATE_REASONING_REQUEST = re.compile(
    r"(?i)\b(?:show|reveal|provide|write|include)\b.{0,60}"
    r"\b(?:chain[- ]of[- ]thought|private reasoning|internal reasoning|private scratchpad)\b"
)


class PromptBundle:
    """Immutable templates loaded from the version-controlled prompt directory."""

    def __init__(self, *, version: str, action: str, language: str, repair: str) -> None:
        if not version:
            raise PromptError("prompt version cannot be empty")
        self.version = version
        self.action = action.strip()
        self.language = language.strip()
        self.repair = repair.strip()
        for name, text in {
            "action": self.action,
            "language": self.language,
            "repair": self.repair,
        }.items():
            if not text:
                raise PromptError(f"{name} prompt cannot be empty")
            if _PRIVATE_REASONING_REQUEST.search(text):
                raise PromptError(f"{name} prompt requests private reasoning")

    @classmethod
    def load(cls, directory: Path, *, version: str = "decision-v1") -> PromptBundle:
        if directory.is_symlink() or not directory.is_dir():
            raise PromptError(f"prompt directory must be a regular directory: {directory}")

        def read(name: str) -> str:
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise PromptError(f"missing prompt template: {path}")
            return path.read_text(encoding="utf-8")

        return cls(
            version=version,
            action=read("v1.action.md"),
            language=read("v1.language.md"),
            repair=read("v1.repair.md"),
        )

    @staticmethod
    def _render(version: str, stage: str, sections: list[str]) -> RenderedPrompt:
        text = "\n\n".join(section.strip() for section in sections if section.strip())
        return RenderedPrompt(
            version=version,
            stage=stage,
            text=text,
            sha256=sha256_value({"stage": stage, "text": text, "version": version}),
        )

    def render_action(self, model_input: ModelInput) -> RenderedPrompt:
        return self._render(
            self.version,
            "action",
            [
                self.action,
                "OUTPUT JSON SCHEMA:\n" + canonical_json(ActionOutput.model_json_schema()),
                "MODEL INPUT:\n" + canonical_json(model_input),
            ],
        )

    def render_language(
        self,
        model_input: ModelInput,
        *,
        chosen_action_id: str,
        action_commitment_sha256: str,
    ) -> RenderedPrompt:
        committed = {
            "action_commitment_sha256": action_commitment_sha256,
            "chosen_action_id": chosen_action_id,
            "event_id": model_input.event_id,
            "run_id": model_input.run_id,
        }
        return self._render(
            self.version,
            "public_language",
            [
                self.language,
                "OUTPUT JSON SCHEMA:\n" + canonical_json(PublicLanguageOutput.model_json_schema()),
                "IMMUTABLE COMMITMENT:\n" + canonical_json(committed),
                "OBSERVABLE FACTS:\n" + canonical_json(model_input.observable_facts),
            ],
        )

    def render_repair(
        self,
        *,
        invalid_response: str,
        output_model: type[RunnerModel],
        original_stage: str,
    ) -> RenderedPrompt:
        return self._render(
            self.version,
            f"{original_stage}_repair",
            [
                self.repair,
                "OUTPUT JSON SCHEMA:\n" + canonical_json(output_model.model_json_schema()),
                "INVALID RESPONSE:\n" + invalid_response,
            ],
        )
