from django.core.cache import cache
from django.test import TestCase, override_settings
from unittest.mock import patch

from user_accounts.models import User
from user_accounts.throttles import LoginRateThrottle


class APIHardeningTests(TestCase):
	def setUp(self):
		cache.clear()

	def test_login_endpoint_applies_scoped_rate_limit(self):
		User.objects.create_user("throttle-user", password="test-password")
		payload = {"username": "throttle-user", "password": "test-password"}

		with patch.object(LoginRateThrottle, "THROTTLE_RATES", {"auth_login": "2/minute"}):
			first_response = self.client.post("/api/auth/token/", payload)
			second_response = self.client.post("/api/auth/token/", payload)
			limited_response = self.client.post("/api/auth/token/", payload)

		self.assertEqual(first_response.status_code, 200)
		self.assertEqual(second_response.status_code, 200)
		self.assertEqual(limited_response.status_code, 429)

	@override_settings(SECURE_HSTS_SECONDS=120)
	def test_security_headers_are_present_on_secure_requests(self):
		response = self.client.get("/api/auth/me/", secure=True)

		self.assertEqual(response.status_code, 401)
		self.assertIn("max-age=120", response["Strict-Transport-Security"])
		self.assertEqual(response["X-Content-Type-Options"], "nosniff")
		self.assertEqual(response["X-Frame-Options"], "DENY")
		self.assertEqual(
			response["Referrer-Policy"],
			"strict-origin-when-cross-origin",
		)

	def test_liveness_does_not_check_dependencies_or_expose_details(self):
		with patch("config.health.database_ready", side_effect=AssertionError):
			with patch("config.health.channel_layer_ready", side_effect=AssertionError):
				response = self.client.get("/health/")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json(), {"status": "ok"})

	def test_readiness_succeeds_when_database_and_channel_layer_are_available(self):
		response = self.client.get("/ready/")

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.json(),
			{
				"status": "ok",
				"dependencies": {"database": "ok", "channel_layer": "ok"},
			},
		)

	def test_readiness_returns_generic_failure_for_unavailable_dependencies(self):
		dependency_states = (
			(False, True, {"database": "unavailable", "channel_layer": "ok"}),
			(True, False, {"database": "ok", "channel_layer": "unavailable"}),
		)
		for database_available, channel_layer_available, expected in dependency_states:
			with self.subTest(dependencies=expected):
				with patch("config.health.database_ready", return_value=database_available):
					with patch("config.health.channel_layer_ready", return_value=channel_layer_available):
						response = self.client.get("/ready/")

				self.assertEqual(response.status_code, 503)
				self.assertEqual(
					response.json(),
					{"status": "unavailable", "dependencies": expected},
				)
