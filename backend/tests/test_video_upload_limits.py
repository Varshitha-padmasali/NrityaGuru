import asyncio

import pytest
from fastapi import HTTPException

from app.api.practice import _decode_video
from app.core.config import Settings
from app.main import PracticeUploadSizeLimit


class FakeCapture:
    def __init__(self, *, fps=10.0, frame_count=20.0, width=320, height=240, reads=20):
        self.values = {5: fps, 7: frame_count, 3: width, 4: height}
        self.reads = reads
        self.released = False

    def isOpened(self):
        return True

    def get(self, key):
        return self.values[key]

    def read(self):
        if self.reads <= 0:
            return False, None
        self.reads -= 1
        return True, object()

    def release(self):
        self.released = True


def test_decoder_checks_frames_and_applies_sample_rate(monkeypatch, tmp_path):
    capture = FakeCapture()
    monkeypatch.setattr("app.api.practice.cv2.VideoCapture", lambda _path: capture)
    sampled, fps = _decode_video(tmp_path / "clip.mp4", Settings(_env_file=None))
    assert sampled == 10
    assert fps == 10.0
    assert capture.released


@pytest.mark.parametrize("kwargs, code", [
    ({"fps": 0.0}, "invalid_video_metadata"),
    ({"frame_count": 0.0}, "invalid_video_metadata"),
    ({"width": 2000, "height": 1200}, "video_resolution_limit"),
    ({"fps": 1.0, "frame_count": 60.0}, "video_duration_limit"),
    ({"reads": 0}, "empty_video"),
    ({"reads": 20}, "video_frame_limit"),
])
def test_decoder_rejects_invalid_or_excessive_video(monkeypatch, tmp_path, kwargs, code):
    capture = FakeCapture(**kwargs)
    monkeypatch.setattr("app.api.practice.cv2.VideoCapture", lambda _path: capture)
    settings = Settings(_env_file=None, max_video_decoded_frames=10 if code == "video_frame_limit" else 5000)
    with pytest.raises(HTTPException) as exc:
        _decode_video(tmp_path / "clip.mp4", settings)
    assert exc.value.detail["code"] == code
    assert capture.released


def test_request_size_middleware_rejects_by_content_length_without_reading_body():
    app_called = False

    async def downstream(_scope, _receive, _send):
        nonlocal app_called
        app_called = True

    middleware = PracticeUploadSizeLimit(downstream, max_request_bytes=10)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/practice/sessions/session-001/video",
        "headers": [(b"content-length", b"11")],
    }
    sent = []

    async def receive():
        raise AssertionError("request body should not be read")

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    assert not app_called
    assert sent[0]["status"] == 413
