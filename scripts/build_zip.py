"""Build a local installation archive; never create tags or publish releases."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anker_solix_extras"


def main() -> None:
    """Package only integration files, ready to extract into custom_components."""
    destination = ROOT / "dist" / "anker_solix_extras.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(COMPONENT.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix in {".pyc", ".pyo"}:
                continue
            archive.write(
                path, Path("anker_solix_extras") / path.relative_to(COMPONENT)
            )
    print(destination)


if __name__ == "__main__":
    main()
