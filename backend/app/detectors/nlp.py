from functools import cached_property
from typing import ClassVar

import spacy
from spacy.language import Language

from app.core.config import settings


class SpacyModelError(RuntimeError):
    pass


class SpacyProvider:
    _cache: ClassVar[dict[str, Language]] = {}

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.spacy_model

    @cached_property
    def nlp(self) -> Language:
        if self.model_name not in self._cache:
            try:
                self._cache[self.model_name] = spacy.load(self.model_name)
            except OSError as exc:
                raise SpacyModelError(
                    f"spaCy model '{self.model_name}' is not installed. "
                    f"Install it with: python -m spacy download {self.model_name}"
                ) from exc
        return self._cache[self.model_name]

    def pipe(self, texts: list[str]):
        return self.nlp.pipe(texts)
