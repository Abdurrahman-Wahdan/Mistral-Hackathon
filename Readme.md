## Interview Agent Production Flow

### 1) Run the Python interview API

```bash
pip install -r requirements.txt
python -m hackathon.api.server
```

Default bind: `0.0.0.0:8081` (configurable from `.env`):

- `INTERVIEW_API_HOST`
- `INTERVIEW_API_PORT`
- `INTERVIEW_API_CORS_ORIGINS`

### 2) Point the UI to the API

In `ui/.env.local`:

```bash
INTERVIEW_AGENT_API_URL=http://localhost:8081
```

Then run UI:

```bash
cd ui
npm install
npm run dev
```

### 3) End-to-end contract used by UI

- `POST /api/interview-session/start`
- `POST /api/interview-session/turn`
- `POST /api/interview-session/finish`
- `POST /api/interview-review` (uses `sessionId` to fetch real report)

Python upstream endpoints:

- `POST /v1/interview/sessions`
- `POST /v1/interview/sessions/{session_id}/turn`
- `POST /v1/interview/sessions/{session_id}/finish`
- `GET /v1/interview/sessions/{session_id}/report`
- `GET /health`
