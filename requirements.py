# FastAPI and associated packages
fastapi == 0.109.2
uvicorn==0.27.1
pydantic==2.6.1
python-dotenv==1.0.1
python-multipart==0.0.9

# Security
python-jose==3.3.0
passlib==1.7.4
bcrypt==4.1.2

# Database
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9  # For PostgreSQL
# SQLite3  # For development

# Google API clients
google-api-python-client==2.115.0
google-auth==2.27.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
google-generativeai==0.4.0

# Twilio for WhatsApp
twilio==8.10.3

# Vector database for context embeddings
chromadb==0.4.22

# Caching
redis==5.0.1

# Utilities
aiohttp==3.9.3
pandas==2.2.0
numpy==1.26.3
pytz==2024.1
Jinja2==3.1.3
python-dateutil==2.8.2
tenacity==8.2.3  # For retrying API calls