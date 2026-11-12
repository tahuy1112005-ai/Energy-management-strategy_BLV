"""Read-only SHA-256 audit of the original 30-day workspace.

All optional audit output is restricted to this new scenario folder.
Run: python verify_original_files.py
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SCENARIO_ROOT = Path(__file__).resolve().parent


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def audit_original_files(*, output_path=None):
    manifest_path = SCENARIO_ROOT / 'original_integrity_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    original_root = Path(manifest['original_root']).resolve()
    changed = []
    missing = []
    for relative, expected in manifest['original_files'].items():
        source = (original_root / relative).resolve()
        if not source.is_relative_to(original_root):
            raise ValueError(f'Original manifest contains a path outside its root: {relative}')
        if not source.is_file():
            missing.append(relative)
        elif source.stat().st_size != expected['bytes'] or sha256_file(source) != expected['sha256']:
            changed.append(relative)
    report = {
        'checked_utc': datetime.now(timezone.utc).isoformat(),
        'original_root': str(original_root),
        'checked_files': len(manifest['original_files']),
        'original_files_unchanged': not changed and not missing,
        'changed_files': changed,
        'missing_files': missing,
        'scope': manifest['scope'],
    }
    if output_path is not None:
        target = Path(output_path).resolve()
        if not target.is_relative_to(SCENARIO_ROOT):
            raise ValueError('Audit output must stay inside the scenario folder.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = audit_original_files(output_path=SCENARIO_ROOT / 'original_integrity_check.json')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['original_files_unchanged'] else 1)
