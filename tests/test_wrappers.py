def test_legacy_wrappers_importable():
    import backend_app.controllers.api  # noqa: F401
    import backend_app.controllers.batch  # noqa: F401
    import backend_app.controllers.web  # noqa: F401
    import backend_app.models.schemas  # noqa: F401
    import backend_app.services.cache  # noqa: F401
    import backend_app.services.jobs  # noqa: F401
    import backend_app.services.nlp  # noqa: F401
    import backend_app.services.processing  # noqa: F401
    import backend_app.services.storage  # noqa: F401
