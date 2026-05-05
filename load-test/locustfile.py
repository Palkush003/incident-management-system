import random
import uuid
from locust import HttpUser, task, between


class IMSSignalUser(HttpUser):
    # Simulated latency between requests
    wait_time = between(0.1, 0.5)

    @task(5)
    def send_random_signal(self):
        """Simulate a high-frequency signal burst from various components."""
        components = [
            ("POSTGRES_PRIMARY", "RDBMS"),
            ("API_GATEWAY_01", "API"),
            ("CACHE_CLUSTER_01", "CACHE"),
            ("KAFKA_BROKER_01", "ASYNC_QUEUE"),
            ("MCP_HOST_01", "MCP_HOST"),
        ]
        comp_id, comp_type = random.choice(components)
        severities = ["P0", "P1", "P2", "P3"]
        
        payload = {
            "component_id": comp_id,
            "component_type": comp_type,
            "severity": random.choice(severities),
            "message": f"Simulated load test error at {uuid.uuid4()}",
            "error_code": f"ERR_{random.randint(1000, 9999)}",
            "metadata": {
                "load_test_id": "LOCUST_RUN_001",
                "vuser_id": str(self.client_id) if hasattr(self, 'client_id') else "unknown"
            }
        }
        
        with self.client.post("/api/v1/signals", json=payload, catch_response=True) as response:
            if response.status_code == 202:
                response.success()
            elif response.status_code == 429:
                # This is actually a success for our backpressure test!
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")

    @task(1)
    def check_dashboard_stats(self):
        """Simulate a user checking the dashboard metrics."""
        self.client.get("/api/v1/dashboard/stats")

    @task(1)
    def list_active_incidents(self):
        """Simulate a responder listing incidents."""
        self.client.get("/api/v1/work-items")
