FROM python:3.12-slim

WORKDIR /app/backend

# Cài đặt các thư viện
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy mã nguồn backend
COPY backend/ .

# Expose port (Gunicorn sẽ chạy ở 5000)
EXPOSE 5000

# Chạy Gunicorn để phục vụ Flask app trong môi trường production với timeout 300s
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "300", "app:app"]