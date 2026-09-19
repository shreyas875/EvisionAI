from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import List, Dict, Any
import asyncio
import json
import datetime
from ..routes.station import get_advanced_realtime_wait_times, get_db
from sqlalchemy.orm import Session

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.update_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

@router.websocket("/ws/realtime-wait-times")
async def websocket_realtime_updates(websocket: WebSocket):
    await manager.connect(websocket)
    
    try:
        while True:
            # Wait for client to send location data
            data = await websocket.receive_text()
            params = json.loads(data)
            
            location = params.get('location', 'Pune')
            battery = params.get('battery', 70)
            charger = params.get('charger', 'CCS2')
            use_real_data = params.get('use_real_data', True)
            
            # Start periodic updates
            update_task = asyncio.create_task(
                periodic_updates(websocket, location, battery, charger, use_real_data)
            )
            manager.update_tasks[websocket] = update_task
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if websocket in manager.update_tasks:
            manager.update_tasks[websocket].cancel()
            del manager.update_tasks[websocket]

async def periodic_updates(websocket: WebSocket, location: str, battery: int, charger: str, use_real_data: bool):
    """Send updates every 10 seconds"""
    while True:
        try:
            # Get fresh data
            db = next(get_db())
            data = await get_advanced_realtime_wait_times(
                location=location,
                battery=battery,
                charger=charger,
                use_real_data=use_real_data,
                db=db
            )
            
            # Send to client
            await manager.send_personal_message(json.dumps(data), websocket)
            
            # Wait 10 seconds
            await asyncio.sleep(10)
            
        except Exception as e:
            error_data = {
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
            await manager.send_personal_message(json.dumps(error_data), websocket)
            await asyncio.sleep(10)
