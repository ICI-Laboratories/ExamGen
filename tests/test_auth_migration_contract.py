from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STREAMLIT_ENTRYPOINTS = [
    ROOT / "app.py",
    ROOT / "pages" / "admin_dashboard.py",
    ROOT / "pages" / "estadisticas_usuario.py",
    ROOT / "pages" / "generar_preguntas.py",
    ROOT / "pages" / "realizar_cuestionario.py",
]


def test_all_streamlit_entrypoints_use_central_auth_only() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in STREAMLIT_ENTRYPOINTS)

    for obsolete_api in ("st.user", "st.login", "st.logout", "experimental_user"):
        assert obsolete_api not in source
    assert source.count("auth.ensure_authenticated(") == len(STREAMLIT_ENTRYPOINTS)


def test_product_identity_and_admin_policy_never_depend_on_email() -> None:
    product_pages = STREAMLIT_ENTRYPOINTS[1:]
    source = "\n".join(path.read_text(encoding="utf-8") for path in product_pages)
    admin_source = (ROOT / "pages" / "admin_dashboard.py").read_text(encoding="utf-8")

    assert "user_email" not in source
    assert "admin_emails" not in source
    assert "auth.is_admin(user_info)" in admin_source
    assert "auth.get_data_identity(user_info)" in STREAMLIT_ENTRYPOINTS[0].read_text(
        encoding="utf-8"
    )
    for path in product_pages:
        # Admin uses only authorization; the three user-data pages resolve the
        # central UUID through the explicit legacy manifest contract.
        if path.name != "admin_dashboard.py":
            assert "auth.get_data_identity(user_info)" in path.read_text(encoding="utf-8")
