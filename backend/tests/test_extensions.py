from app.extensions import CommunityExtension, load_extension


def test_community_extension_is_the_default(monkeypatch):
    monkeypatch.delenv("CAUSALITY_EXTENSION_MODULE", raising=False)
    extension = load_extension()
    assert isinstance(extension, CommunityExtension)
    assert extension.routers == []
