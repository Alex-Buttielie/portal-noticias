class FakeProvider:
    def create_checkout(self, plan, user, success_url, cancel_url):
        return {"url": f"{success_url}?fake=1&plan={plan.get('id')}", "session_id": "fake_123"}
    def handle_webhook(self, request):
        import json
        b = json.loads(request.body or "{}")
        return {"payment_id": b.get("id","fake_1"), "status": "approved", "plan_id": b.get("plan_id","semestral"), "user_id": b.get("user_id","u1"), "amount": 2000}
    def refund(self, payment_id): return None
    def get_status(self, payment_id): return "approved"
