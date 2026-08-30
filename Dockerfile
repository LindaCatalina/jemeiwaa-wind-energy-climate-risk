FROM python:3.12-slim-bookworm

WORKDIR /opt/jemeiwaa
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# .dockerignore excluye datos crudos, secretos y resultados legados redundantes.
COPY . .

CMD ["python", "run_portfolio.py", "--check-only"]
