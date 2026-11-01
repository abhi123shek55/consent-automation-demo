# Consent Automation — demo edition

## Run locally
Use Python 3.12. Open a terminal inside this folder.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. Dependencies are installed fresh; a Windows virtual environment is intentionally not bundled.

## Deploy on Render
Upload the contents of this folder to a Git repository. Create a Render Web Service connected to it. Use Python runtime, build command `pip install -r requirements.txt`, and start command `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 60`. Alternatively use the included render.yaml blueprint. Health check: `/health`.
If this folder is nested in your repository, set it as the service root directory.
Free instances can sleep when idle. Review current limits before deployment.

## Demo scope
No database is required. The application processes inputs in memory and returns downloads; it does not intentionally store uploaded content. Hosting infrastructure may retain request metadata. Use sample data only.

The template uses RESEARCH_COMPANY, Contact 1–7, example.com addresses, placeholder telephone values and a placeholder access token. External API and email logic has `cond="0"`. Exit URLs point to example.com. The former logo path is blank. This is a demonstration of generation, not a ready-to-field consent project or reviewed legal text.

Use “Try sample project”, then generate the XML. The original country/contact assignment and optional-clause workflow are retained. One-country projects retain a second country row as in the original implementation. Decipher syntax includes prefixed attributes without namespace declarations; a generic strict XML parser may reject these. Validate the generated survey in your target Decipher environment before field use.
