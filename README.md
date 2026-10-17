# CU Nearby Stock

Mobile web app: FastAPI + Kakao Maps JavaScript SDK.

## Deploy on Render (Free)

Use the included render.yaml as a Render Blueprint.
Set KAKAO_JS_KEY to your Kakao JavaScript key in Render.
SESSION_SECRET is generated automatically. COOKIE_SECURE=1 is required on HTTPS.

For a manual Web Service:
- Runtime: Python 3 (PYTHON_VERSION=3.14.0)
- Build: pip install -r requirements.txt
- Start: uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
- Health check: /health
- Plan: Free

Add your final https://...onrender.com origin to the Kakao JavaScript SDK domains.
Enable Kakao Map API usage for the same app.
Verify CU product and stock connectivity again from the deployed server.
Local success does not guarantee access from Render.

GPS is requested once per button press, with no continuous tracking.
Product cache: 10 minutes. Stock cache: 30 seconds in process memory.
Requests: 10 per minute per anonymous browser session, plus an IP guard.
No automatic retries. No login, notifications, or favorites.
Free services sleep when idle; allow time for the first request.
