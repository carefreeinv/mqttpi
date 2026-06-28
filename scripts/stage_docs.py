#!/usr/bin/env python3
"""Stage repository markdown into docs/ for MkDocs."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = ROOT / "site_assets"
REPO_BASE = "https://github.com/carefreeinv/mqttpi/blob/main"

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def repo_to_docs(rel: Path) -> str | None:
    if rel.suffix != ".md":
        return None
    if rel == Path("README.md"):
        return "index.md"
    if rel == Path("CHANGELOG.md"):
        return "changelog.md"
    if rel == Path("config.example.md"):
        return "configuration.md"
    if len(rel.parts) == 3 and rel.parts[0] == "projects" and rel.name == "README.md":
        return f"projects/{rel.parent.name}.md"
    parts = list(rel.parts)
    if parts[0] == "examples" and rel.name == "README.md":
        return "examples/index.md"
    if parts[0] == "examples":
        return str(Path("examples", *parts[1:]))
    return None


def resolve_href(src: Path, href: str) -> Path:
    if href.startswith("examples/") or href.startswith("projects/"):
        return (ROOT / href).resolve()
    return (src.parent / href).resolve()


def docs_relative_path(src: Path, href: str, dst: Path) -> str | None:
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return None
    resolved = resolve_href(src, href)
    try:
        rel = resolved.relative_to(ROOT)
    except ValueError:
        return None
    docs_target = repo_to_docs(rel)
    if docs_target is None:
        return None
    return Path(os.path.relpath(DOCS / docs_target, dst.parent)).as_posix()


def rewrite_links(text: str, src: Path, dst: Path) -> str:
    replacements = {
        "](examples/README.md)": "](examples/index.md)",
        "](CHANGELOG.md)": "](changelog.md)",
        "](config.example.md)": "](configuration.md)",
        "../projects/cargo-trailer/README.md": "../projects/cargo-trailer.md",
        "projects/cargo-trailer/README.md": "projects/cargo-trailer.md",
        "](../../examples/sites/": "](../examples/sites/",
        "](examples/)": "](examples/index.md)",
        "](examples/sites/)": "](examples/index.md#site-templates-sites)",
        "](LICENSE)": f"]({REPO_BASE}/LICENSE)",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    def replace_link(match: re.Match[str]) -> str:
        label, href = match.group(1), match.group(2)
        if href.endswith(".yaml"):
            resolved = resolve_href(src, href)
            try:
                rel = resolved.relative_to(ROOT)
            except ValueError:
                return match.group(0)
            return f"[{label}]({REPO_BASE}/{rel.as_posix()})"
        docs_href = docs_relative_path(src, href, dst)
        if docs_href is not None:
            return f"[{label}]({docs_href})"
        return match.group(0)

    return LINK_PATTERN.sub(replace_link, text)


def copy_md(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(rewrite_links(src.read_text(encoding="utf-8"), src, dst), encoding="utf-8")


def write_pages(path: Path, title: str) -> None:
    path.write_text(f"title: {title}\n", encoding="utf-8")


def stage_examples() -> None:
    examples_src = ROOT / "examples"
    examples_dst = DOCS / "examples"

    copy_md(examples_src / "README.md", examples_dst / "index.md")

    generic = [
        "maximum-gpio.md",
        "digital-in-out.md",
        "multi-relay.md",
        "relay-bank-16.md",
        "speaker-zones-8.md",
        "pwm-bank.md",
        "servo-controller.md",
        "analog-inputs.md",
        "garage-door.md",
        "home-assistant.md",
        "sensors-i2c-onewire.md",
        "full-peripherals.md",
        "pi4-maximum-gpio.md",
        "pi4-pwm-relay.md",
        "relay-bank-32.md",
        "robot.md",
    ]
    protocols = [
        "jbd-bms.md",
        "level-accelerometer.md",
        "tpms.md",
        "can-vehicle.md",
        "can-rvc.md",
        "can-can2040.md",
        "victron-vedirect.md",
        "victron-vecan.md",
    ]
    sites = sorted(path.name for path in (examples_src / "sites").glob("*.md"))

    for name in generic + protocols:
        copy_md(examples_src / name, examples_dst / name)
    for name in sites:
        copy_md(examples_src / "sites" / name, examples_dst / "sites" / name)

    examples_nav = "\n".join(
        [
            "title: Examples",
            "nav:",
            "  - index.md",
            "  - Generic:",
            *[f"      - {name}" for name in generic],
            "  - Protocols:",
            *[f"      - {name}" for name in protocols],
            "  - Site templates:",
            "      - sites",
            "",
        ]
    )
    (examples_dst / ".pages").write_text(examples_nav, encoding="utf-8")
    write_pages(examples_dst / "sites" / ".pages", "Site templates")


def main() -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()

    copy_md(ROOT / "README.md", DOCS / "index.md")
    copy_md(ROOT / "CHANGELOG.md", DOCS / "changelog.md")
    copy_md(ROOT / "config.example.md", DOCS / "configuration.md")
    copy_md(ROOT / "projects" / "cargo-trailer" / "README.md", DOCS / "projects" / "cargo-trailer.md")

    stage_examples()

    root_nav = "\n".join(
        [
            "nav:",
            "  - index.md",
            "  - configuration.md",
            "  - examples",
            "  - projects",
            "  - changelog.md",
            "",
        ]
    )
    (DOCS / ".pages").write_text(root_nav, encoding="utf-8")
    write_pages(DOCS / "projects" / ".pages", "Deployment guides")

    styles_dst = DOCS / "stylesheets"
    styles_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy(ASSETS / "extra.css", styles_dst / "extra.css")


if __name__ == "__main__":
    main()