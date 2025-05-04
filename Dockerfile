FROM python:3.12

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port=8080", "--server.address=0.0.0.0"] 