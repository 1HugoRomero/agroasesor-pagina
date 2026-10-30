"""Verifica integridad local del YAML. NO es un sello oficial del SAG/INIA/ODEPA."""

import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'data' / 'catalogo_agricola.yaml'
manifest = root / 'data' / 'catalogo_agricola.sha256'
actual = hashlib.sha256(source.read_bytes()).hexdigest()
expected = manifest.read_text(encoding='utf-8').strip().split()[0]
if actual != expected:
    raise SystemExit('ERROR: catálogo modificado respecto de la huella SHA-256 del borrador.')
print('OK: integridad local del archivo YAML. Esto NO es una certificación institucional.')
