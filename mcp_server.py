#!/usr/bin/env python3
"""
EOS CRM - Servidor MCP
Permite a Claude acceder al CRM de EOS en tiempo real.
"""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

CRM_BASE = os.environ.get("CRM_BASE_URL", "https://crm-eos-production.up.railway.app")
CRM_USER = os.environ.get("CRM_USERNAME", "admin")
CRM_PASS = os.environ.get("CRM_PASSWORD", "")

mcp = FastMCP("EOS CRM")
_auth_token = None


async def get_token():
    global _auth_token
    if _auth_token:
        return _auth_token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CRM_BASE}/api/auth/login",
            json={"username": CRM_USER, "password": CRM_PASS},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _auth_token = data.get("token") or data.get("access_token")
        if not _auth_token:
            raise ValueError(f"Login fallido: {data}")
        return _auth_token


async def crm(method, path, **kwargs):
    global _auth_token
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method, f"{CRM_BASE}/api{path}", headers=headers, timeout=15, **kwargs
        )
        if resp.status_code == 401:
            _auth_token = None
            token = await get_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.request(
                method, f"{CRM_BASE}/api{path}", headers=headers, timeout=15, **kwargs
            )
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def listar_cuentas():
    """Lista todas las cuentas del CRM de EOS (clientes y prospectos)."""
    data = await crm("GET", "/accounts")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_contactos(account_id=None):
    """Lista los contactos. Si se indica account_id, filtra por esa cuenta."""
    path = f"/contacts?account_id={account_id}" if account_id else "/contacts"
    data = await crm("GET", path)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_visitas(limite=20):
    """Lista las ultimas visitas comerciales registradas en el CRM."""
    data = await crm("GET", "/visits")
    if isinstance(data, list):
        data = data[:limite]
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_acciones(estado="todas"):
    """Lista acciones/tareas. estado: 'pendiente', 'hecha', o 'todas'."""
    data = await crm("GET", "/actions")
    if isinstance(data, list) and estado != "todas":
        data = [a for a in data if a.get("status") == estado]
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_notas():
    """Lista todas las anotaciones del CRM."""
    data = await crm("GET", "/notes")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def obtener_estadisticas():
    """Resumen: cuentas totales, visitas del mes, acciones pendientes y vencidas."""
    data = await crm("GET", "/admin/stats")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def crear_visita(account_id, fecha, tipo, resumen, resultado, proxima_accion="", productos_hablados=""):
    """
    Registra una visita comercial.
    tipo: 'presencial' o 'telefonica'
    resultado: 'pendiente', 'cerrado' o 'no_interesado'
    fecha: formato YYYY-MM-DDTHH:MM
    """
    data = await crm("POST", "/visits", json={
        "account_id": account_id, "date": fecha, "type": tipo,
        "summary": resumen, "result": resultado,
        "next_action": proxima_accion, "products_discussed": productos_hablados,
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def crear_accion(titulo, account_id, fecha_limite, prioridad="media", descripcion=""):
    """
    Crea una tarea de seguimiento.
    prioridad: 'alta', 'media' o 'baja'
    fecha_limite: formato YYYY-MM-DD
    """
    data = await crm("POST", "/actions", json={
        "title": titulo, "account_id": account_id,
        "due_date": fecha_limite, "priority": prioridad,
        "description": descripcion, "status": "pendiente",
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"EOS CRM MCP Server arrancando en puerto {port}...")
    mcp.run(transport="sse", host="0.0.0.0", port=port)
