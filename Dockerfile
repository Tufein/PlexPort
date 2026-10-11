FROM python:3.13-slim
WORKDIR /app
COPY plexport /app/plexport
ENV PYTHONUNBUFFERED=1 PLEXPORT_HOST=0.0.0.0 PLEXPORT_DATA=/data PLEXPORT_DOWNLOADS=/downloads PLEXPORT_MEDIA=/media
EXPOSE 8765
CMD ["python", "-m", "plexport"]
