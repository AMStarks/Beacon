import re
from typing import List, Dict

try:
    import spacy
except Exception:
    spacy = None  # Optional dependency; handled by caller


class EntityResolver:
    """Lightweight entity normalization and alias handling.

    - Uses spaCy NER if available
    - Applies simple normalization rules
    - Resolves common aliases (teams, orgs, people initials)
    """

    def __init__(self):
        self._nlp = None
        if spacy is not None:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except Exception:
                self._nlp = None

        # Minimal alias map; can be expanded or backed by a DB/Wikidata
        self.alias_map: Dict[str, str] = {
            "SF 49ers": "San Francisco 49ers",
            "49ers": "San Francisco 49ers",
            "Cowboys": "Dallas Cowboys",
            "US": "United States",
            "U.S.": "United States",
            "USA": "United States",
            "UK": "United Kingdom",
            "U.K.": "United Kingdom",
            "UN": "United Nations",
        }

    def normalize_entity(self, name: str) -> str:
        if not name:
            return name
        # Trim and collapse whitespace
        norm = re.sub(r"\s+", " ", name).strip()

        # Title-case multiword entities but keep known uppercase acronyms
        if norm.upper() in {"USA", "US", "U.S.", "UK", "U.K.", "UN", "EU", "NATO"}:
            norm = norm.upper().replace("U.S.", "U.S.")
        else:
            # Keep casing for brands like iPhone by skipping all-lower heuristics
            if not re.search(r"[a-z][A-Z]", norm):
                norm = " ".join(w if w.isupper() else w.capitalize() for w in norm.split())

        # Apply alias mapping
        if norm in self.alias_map:
            return self.alias_map[norm]

        # Remove trailing punctuation
        norm = norm.rstrip(".,:;-")
        return norm

    def normalize_entities(self, entities: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for e in entities:
            n = self.normalize_entity(e)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    def extract_entities(self, text: str) -> List[str]:
        if not text:
            return []
        if self._nlp is None:
            # Fallback: naive proper-noun sequences
            return re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text)
        doc = self._nlp(text)
        entities: List[str] = []
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "NORP", "EVENT", "WORK_OF_ART"}:
                entities.append(ent.text)
        return entities


