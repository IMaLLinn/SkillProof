"""Request guard integration tests over ASGI, including streamed request bodies."""

import unittest

from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


class RequestGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        settings = Settings(
            environment="development", cookie_secure=True,
            allowed_hosts=("testserver",), origin="https://testserver", max_body_bytes=16,
        )
        self.client = await self.enterAsyncContext(AsyncClient(
            transport=ASGITransport(app=create_app(settings)), base_url="https://testserver",
        ))

    async def test_invalid_and_negative_content_length_returns_400(self):
        for declared in ("invalid", "-1"):
            with self.subTest(content_length=declared):
                response = await self.client.post(
                    "/api/auth/login", json={}, headers={"Content-Length": declared},
                )
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json(), {"detail": "无效的请求长度"})

    async def test_oversized_body_without_content_length_returns_413(self):
        request = self.client.build_request("POST", "/api/auth/login", content=b"x" * 17)
        del request.headers["content-length"]
        self.assertNotIn("transfer-encoding", request.headers)

        response = await self.client.send(request)
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json(), {"detail": "请求内容过大"})

    async def test_cumulative_size_of_chunked_body_returns_413(self):
        async def chunks():
            yield b"x" * 8
            yield b"y" * 9

        request = self.client.build_request("POST", "/api/auth/login", content=chunks())
        self.assertNotIn("content-length", request.headers)
        self.assertEqual(request.headers["transfer-encoding"], "chunked")

        response = await self.client.send(request)
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json(), {"detail": "请求内容过大"})

    async def test_secure_cookie_mode_sets_hsts(self):
        response = await self.client.get("/api/health")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["strict-transport-security"], "max-age=31536000")
