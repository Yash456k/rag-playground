from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
PUBLIC_SITE = "https://www.yash456k.com/"
LEGACY_VERCEL_SITE = "https://rag-playground-alpha.vercel.app/"


def test_frontend_metadata_uses_public_portfolio_domain() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert f'<link rel="canonical" href="{PUBLIC_SITE}" />' in html
    assert f'<meta property="og:url" content="{PUBLIC_SITE}" />' in html
    assert LEGACY_VERCEL_SITE not in html
