#!/usr/bin/env python3
"""EOS CRM - Servidor MCP. Permite a Claude acceder al CRM de EOS en tiempo real."""

import os, json, uvicorn
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

CRM_BASE = os.environ.get("CRM_BASE_URL", "https://crm-eos-production.up.railway.app")
CRM_USER = os.environ.get("CRM_USERNAME", "admin")
CRM_PASS = os.environ.get("CRM_PASSWORD", "")

mcp = FastMCP("EOS CRM")
_auth_token: str | None = None


async def get_token() -> str:
    global _auth_token
    if _auth_token:
        return _auth_token
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{CRM_BASE}/api/auth/login",
            json={"username": CRM_USER, "password": CRM_PASS}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        _auth_token = data.get("token") or data.get("access_token")
        if not _auth_token:
            raise ValueError(f"Login fallido: {data}")
        return _auth_token


async def crm(method: str, path: str, **kwargs) -> Any:
    global _auth_token
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.request(method, f"{CRM_BASE}/api{path}",
            headers=headers, timeout=15, **kwargs)
        if resp.status_code == 401:
            _auth_token = None
            token = await get_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.request(method, f"{CRM_BASE}/api{path}",
                headers=headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def listar_cuentas() -> str:
    """Lista todas las cuentas (clientes y prospectos) del CRM de EOS."""
    return json.dumps(await crm("GET", "/accounts"), ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_contactos(account_id: int | None = None) -> str:
    """Lista contactos del CRM. Si se indica account_id, filtra por esa cuenta."""
    path = f"/contacts?account_id={account_id}" if account_id else "/contacts"
    return json.dumps(await crm("GET", path), ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_visitas(limite: int = 20) -> str:
    """Lista las ultimas visitas comerciales registradas."""
    data = await crm("GET", "/visits")
    if isinstance(data, list):
        data = data[:limite]
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_acciones(estado: str = "todas") -> str:
    """Lista acciones/tareas. estado: 'pendiente', 'hecha', o 'todas'."""
    data = await crm("GET", "/actions")
    if isinstance(data, list) and estado != "todas":
        data = [a for a in data if a.get("status") == estado]
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_notas() -> str:
    """Lista todas las anotaciones del CRM."""
    return json.dumps(await crm("GET", "/notes"), ensure_ascii=False, indent=2)


@mcp.tool()
async def obtener_estadisticas() -> str:
    """Resumen: cuentas totales, visitas del mes, acciones pendientes y vencidas."""
    return json.dumps(await crm("GET", "/admin/stats"), ensure_ascii=False, indent=2)


@mcp.tool()
async def crear_visita(account_id: int, fecha: str, tipo: str, resumen: str,
    resultado: str, proxima_accion: str = "", productos_hablados: str = "") -> str:
    """Registra una visita. tipo: 'presencial'/'telefonica'. resultado: 'pendiente'/'cerrado'/'no_interesado'."""
    return json.dumps(await crm("POST", "/visits", json={
        "account_id": account_id, "date": fecha, "type": tipo,
        "summary": resumen, "result": resultado,
        "next_action": proxima_accion, "products_discussed": productos_hablados,
    }), ensure_ascii=False, indent=2)


@mcp.tool()
async def crear_accion(titulo: str, account_id: int, fecha_limite: str,
    prioridad: str = "media", descripcion: str = "") -> str:
    """Crea una tarea de seguimiento. prioridad: 'alta'/'media'/'baja'."""
    return json.dumps(await crm("POST", "/actions", json={
        "title": titulo, "account_id": account_id, "due_date": fecha_limite,
        "priority": prioridad, "description": descripcion, "status": "pendiente",
    }), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"EOS CRM MCP Server arrancando en puerto {port}...")
    # Usar uvicorn directamente para control total de host/port
    app = mcp.get_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
