FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY servidor_mcp.py .
# en el contenedor debe escuchar en todas las interfaces; el acceso lo controla MCP_TOKEN
ENV MCP_HOST=0.0.0.0
EXPOSE 9000
CMD ["python", "servidor_mcp.py"]
