FROM python:3.11-slim

# Asboblarni to'g'ridan-to'g'ri ishonchli ombordan olamiz
RUN apt-get update && apt-get install -y ffmpeg

# Ish xonasini tayyorlaymiz
WORKDIR /app

# Kutubxonalarni o'rnatamiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarimizni xonaga joylaymiz
COPY . .

# Botni ishga tushiramiz
CMD ["python", "main.py"]
