# 🌍 Travel Planning & Experience Engine

AI-powered trip planner that generates personalized day-by-day itineraries using Google Gemini, Google Maps, and real-time weather data. Built for **PromptWars Hyderabad 2026**.

## ✨ Features

- **AI-Powered Planning** — Google Gemini generates tailored itineraries from your preferences
- **Google Maps Integration** — Real venue data, ratings, photos, and interactive route maps
- **Weather-Aware Scheduling** — Automatically swaps outdoor activities when bad weather is forecast
- **Budget Tracking** — Real-time budget allocation and overflow detection with AI rebalancing
- **Chat Refinement** — Modify your itinerary with natural language ("make day 2 more relaxed")
- **Disruption Handling** — Mark venues as unavailable and get instant AI-generated replacements
- **Calendar Export** — One-click .ics file download for Google Calendar
- **Accessible UI** — WCAG 2.1 AA compliant with keyboard navigation and screen reader support

## 🏗️ Architecture

```
Single Docker Container → Google Cloud Run (port 8080)
├── FastAPI (Python 3.12) — async API + HTML rendering
├── Jinja2 + HTMX — interactive UI without JS framework
├── TailwindCSS (CDN) — responsive styling, zero build step
├── Google Gemini 1.5 Flash — AI planning & refinement
├── Google Maps/Places — venue search, routes, geocoding
├── Open-Meteo — weather forecasts (free, no key required)
├── Firestore — persistence (in-memory fallback for dev)
└── iCalendar — .ics export for Google Calendar
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Google Gemini API key ([Get one free](https://aistudio.google.com/app/apikey))
- Google Maps API key ([Console](https://console.cloud.google.com/apis/credentials))

### Local Development

```bash
# Clone and enter the project
git clone https://github.com/your-username/promptwars-challenge.git
cd promptwars-challenge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the server
uvicorn app.main:app --reload --port 8080

# Open http://localhost:8080
```

### Docker

```bash
docker build -t travel-engine .
docker run -p 8080:8080 --env-file .env travel-engine
```

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test categories
pytest tests/test_models.py -v          # Model validation
pytest tests/test_google_services.py -v # Google services (mocked)
pytest tests/test_planner.py -v         # AI planning engine
pytest tests/test_api.py -v             # API endpoints
pytest tests/test_storage.py -v         # Persistence layer
pytest tests/test_integration.py -v     # Integration & edge cases
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Landing page with preference form |
| `GET` | `/health` | Health check (Cloud Run) |
| `POST` | `/api/plan` | Generate new itinerary |
| `GET` | `/api/plan/{id}` | Get itinerary JSON |
| `GET` | `/api/plan/{id}/day/{n}` | Get day view (HTMX partial) |
| `POST` | `/api/plan/{id}/refine` | Refine via natural language |
| `POST` | `/api/plan/{id}/disrupt` | Replace disrupted slot |
| `GET` | `/api/plan/{id}/export` | Download .ics calendar file |

## ☁️ Cloud Run Deployment

```bash
# Set your project
export GOOGLE_CLOUD_PROJECT=your-project-id

# Deploy (requires gcloud CLI)
./deploy.sh
```

Or manually:

```bash
gcloud run deploy travel-engine \
    --source . \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi \
    --max-instances 3
```

## 🏆 Judging Criteria Alignment

| Criterion | Implementation |
|-----------|---------------|
| **Code Quality** | Clean architecture, type hints, Pydantic models, docstrings |
| **Security** | Input validation, no secrets in code, env-var configuration |
| **Efficiency** | Async I/O, structured Gemini output, minimal API calls |
| **Testing** | 70+ tests: unit, integration, edge cases |
| **Accessibility** | WCAG 2.1 AA, ARIA labels, keyboard navigation, skip links |
| **Google Services** | Gemini AI, Google Maps, Places API, Calendar export |

## 📁 Project Structure

```
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py             # Pydantic settings
│   ├── routes/
│   │   ├── api.py            # REST API endpoints
│   │   └── pages.py          # HTML page routes
│   ├── models/
│   │   ├── preferences.py    # User input models
│   │   ├── itinerary.py      # Trip data models
│   │   └── constraints.py    # Validation models
│   ├── services/
│   │   ├── planner.py        # Gemini AI planning
│   │   ├── constraints.py    # Budget & schedule validation
│   │   ├── google_maps.py    # Maps & Places APIs
│   │   ├── google_calendar.py# .ics export
│   │   ├── weather.py        # Open-Meteo forecasts
│   │   └── firestore.py      # Persistence layer
│   ├── templates/            # Jinja2 HTML templates
│   └── static/               # JS, CSS
├── tests/                    # Pytest test suite
├── Dockerfile                # Cloud Run container
├── requirements.txt          # Python dependencies
└── deploy.sh                 # One-click Cloud Run deploy
```

## 📄 License

Built for PromptWars Hyderabad 2026 Hackathon.
