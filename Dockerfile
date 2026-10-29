FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home resive
COPY --chown=resive:resive . .
USER resive
EXPOSE 8000
CMD ["sh", "-c", "python manage.py collectstatic --noinput && waitress-serve --listen=0.0.0.0:8000 config.wsgi:application"]
