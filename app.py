"""Entrada ASGI para hospedagem serverless (Vercel), em HTTP no caminho /mcp.

A Vercel procura um `app` em app.py. Em serverless cada requisição pode cair numa
instância nova, então o servidor roda sem sessão guardada (stateless_http=True).
Para testar localmente: uvicorn app:app --port 8000
"""
from servidor_prazos import mcp

app = mcp.http_app(stateless_http=True)
