"""MkDocs hook — set dynamic copyright footer year at build time."""

from datetime import datetime


def on_config(config, **kwargs):
    year = datetime.now().year
    config.copyright = (
        f'© Copyright <a href="https://carefreeinv.com" target="_blank" '
        f'rel="noopener">Carefree Investments</a> {year}'
    )