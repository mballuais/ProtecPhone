import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "livrables"


def main():
    required = ["rapport/ProtecPhone-Rapport-NoSQL.pdf", "docs/validation/result.json", "livrables/REMISE-MOODLE.md"]
    for name in required:
        if not (ROOT / name).is_file():
            raise RuntimeError("Livrable absent : " + name)
    result = json.loads((ROOT / "docs/validation/result.json").read_text(encoding="utf-8"))
    if result["exit_code"] != 0:
        raise RuntimeError("La derniere validation a echoue")
    roots = ["src", "scripts", "docs", "rapport"]
    files = [p for folder in roots for p in (ROOT / folder).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts
             and p.suffix in {".java", ".properties", ".py", ".md", ".json", ".pdf", ".txt", ".log"}]
    root_names = ["README.md", "Redis-Hash-Commande.md", "pom.xml", "Dockerfile", "docker-compose.yml", "ListEvents", ".gitignore", ".dockerignore"]
    files += [ROOT / name for name in root_names]
    files += list(ROOT.glob("*.json"))
    files += list(DEST.glob("*.md"))
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(set(files))}
    (DEST / "MANIFEST-SHA256.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive = DEST / "ProtecPhone-Rendu-NoSQL.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for name in manifest:
            output.write(ROOT / name, "ProtecPhone/" + name)
        output.write(DEST / "MANIFEST-SHA256.json", "ProtecPhone/livrables/MANIFEST-SHA256.json")
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        assert all("/.git/" not in name and "/target/" not in name and "/.env" not in name for name in check.namelist())
        for name, expected in manifest.items():
            assert hashlib.sha256(check.read("ProtecPhone/" + name)).hexdigest() == expected, name
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (DEST / "ProtecPhone-Rendu-NoSQL.zip.sha256").write_text(digest + "  " + archive.name + "\n", encoding="ascii")
    print(f"OK : {len(manifest)} fichiers, {archive.stat().st_size} octets ; {archive.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
