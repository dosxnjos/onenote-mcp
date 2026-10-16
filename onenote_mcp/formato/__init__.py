"""formato ONMD (markdown do OneNote): escrita (ONMD → HTML), leitura (HTML do OneNote → ONMD) e paleta.
spec para a IA em spec.md (servida por ler_spec e pelo recurso onenote://docs/formato)."""
from pathlib import Path

SPEC = Path(__file__).resolve().parent / "spec.md"


def ler_spec():
    return SPEC.read_text(encoding="utf-8")
