FROM python:3.13-slim
WORKDIR /app
COPY jellyport /app/jellyport
ENV PYTHONUNBUFFERED=1 JELLYPORT_HOST=0.0.0.0 JELLYPORT_DATA=/data JELLYPORT_DOWNLOADS=/downloads JELLYPORT_MEDIA=/media
EXPOSE 8765
CMD ["python", "-m", "jellyport"]
