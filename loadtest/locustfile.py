import os
import random

from locust import HttpUser, between, task

API_KEY = os.environ["LOAD_TEST_KEY"]
MONITOR_IDS = list(range(1, 5001))


class SentinelUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def list_monitors(self):
        self.client.get(
            "/v1/monitors?limit=50",
            headers={"X-API-Key": API_KEY},
            name="GET /v1/monitors",
        )

    @task(2)
    def monitor_stats(self):
        monitor_id = random.choice(MONITOR_IDS)
        self.client.get(
            f"/v1/monitors/{monitor_id}/stats",
            headers={"X-API-Key": API_KEY},
            name="GET /v1/monitors/:id/stats",
        )

    @task(1)
    def recent_checks(self):
        monitor_id = random.choice(MONITOR_IDS)
        self.client.get(
            f"/v1/monitors/{monitor_id}/checks?limit=50",
            headers={"X-API-Key": API_KEY},
            name="GET /v1/monitors/:id/checks",
        )
