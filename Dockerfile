FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# The app is standard library only: nothing to pip install.
COPY gardener ./gardener

RUN useradd --create-home app
USER app

ENV PORT=8000
EXPOSE 8000
CMD ["python", "-m", "gardener", "serve"]
