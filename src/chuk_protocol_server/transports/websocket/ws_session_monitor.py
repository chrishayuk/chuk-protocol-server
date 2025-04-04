#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_session_monitor.py
"""
WebSocket Session Monitor

This module provides functionality to monitor WebSocket sessions by broadcasting
client activities to a separate channel where viewers can connect and observe.
"""
import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, List

# websockets
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# logger
logger = logging.getLogger('chuk-protocol-server')

class SessionMonitor:
    """
    Session monitor that broadcasts session activities to connected viewers.
    
    This class maintains a registry of active sessions and viewers, and
    provides methods to broadcast session events to viewers.
    """
    
    def __init__(self, path: str = '/monitor'):
        """
        Initialize the session monitor.
        
        Args:
            path: The WebSocket path for the monitoring endpoint
        """
        self.path = path
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.session_viewers: Dict[str, Set[WebSocketServerProtocol]] = {}
        self.all_viewers: Set[WebSocketServerProtocol] = set()
        self._lock = asyncio.Lock()
    
    def is_monitor_path(self, path: str) -> bool:
        """
        Check if a path is the monitoring path.
        
        Args:
            path: The path to check
            
        Returns:
            True if the path is the monitoring path, False otherwise
        """
        expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
        return path == expected_path
    
    async def register_session(self, session_id: str, client_info: Dict[str, Any]) -> None:
        """
        Register a new session to be monitored.
        
        Args:
            session_id: The unique ID of the session
            client_info: Information about the client (e.g., IP, port)
        """
        async with self._lock:
            # Mark all existing sessions as not newest
            for existing_id in self.active_sessions:
                if 'is_newest' in self.active_sessions[existing_id]:
                    self.active_sessions[existing_id]['is_newest'] = False
            
            # Create new session info with is_newest flag
            self.active_sessions[session_id] = {
                'id': session_id,
                'client': client_info,
                'start_time': asyncio.get_event_loop().time(),
                'status': 'connected',
                'is_newest': True  # Mark as newest session
            }
            self.session_viewers[session_id] = set()
            
            # Broadcast new session to all viewers
            await self._broadcast_to_all_viewers({
                'type': 'session_started',
                'session': self.active_sessions[session_id]
            })
            
            logger.info(f"Session {session_id} registered for monitoring (newest)")
    
    async def unregister_session(self, session_id: str) -> None:
        """
        Unregister a session from monitoring.
        
        Args:
            session_id: The unique ID of the session
        """
        async with self._lock:
            if session_id in self.active_sessions:
                session_info = self.active_sessions[session_id]
                session_info['status'] = 'disconnected'
                
                # Broadcast session end to all viewers
                await self._broadcast_to_all_viewers({
                    'type': 'session_ended',
                    'session': session_info
                })
                
                # Notify session-specific viewers
                await self._broadcast_to_session_viewers(session_id, {
                    'type': 'session_ended',
                    'session': session_info
                })
                
                # Clean up
                self.active_sessions.pop(session_id, None)
                self.session_viewers.pop(session_id, None)
                
                logger.info(f"Session {session_id} unregistered from monitoring")
    
    async def broadcast_session_event(self, session_id: str, event_type: str, data: Any) -> None:
        """
        Broadcast a session event to viewers.
        
        Args:
            session_id: The unique ID of the session
            event_type: The type of event
            data: The event data
        """
        if session_id not in self.active_sessions:
            return
        
        message = {
            'type': event_type,
            'session_id': session_id,
            'data': data
        }
        
        await self._broadcast_to_session_viewers(session_id, message)
    
    async def handle_viewer_connection(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new viewer connection.
        
        Args:
            websocket: The WebSocket connection
        """
        # Add to all viewers set
        self.all_viewers.add(websocket)
        
        # Send list of active sessions
        await self._send_active_sessions(websocket)
        
        try:
            # Process viewer commands
            async for message in websocket:
                try:
                    if isinstance(message, str):
                        command = json.loads(message)
                        await self._process_viewer_command(websocket, command)
                    else:
                        logger.warning(f"Received binary message from viewer, ignoring")
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from viewer: {message}")
                except Exception as e:
                    logger.error(f"Error processing viewer command: {e}")
        
        except ConnectionClosed:
            logger.info(f"Viewer connection closed")
        finally:
            # Remove from all sets
            self.all_viewers.discard(websocket)
            for viewers in self.session_viewers.values():
                viewers.discard(websocket)
    
    async def _send_active_sessions(self, websocket: WebSocketServerProtocol) -> None:
        """
        Send the list of active sessions to a viewer.
        
        Args:
            websocket: The WebSocket connection
        """
        sessions = list(self.active_sessions.values())
        message = {
            'type': 'active_sessions',
            'sessions': sessions
        }
        try:
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending active sessions: {e}")
    
    async def _process_viewer_command(self, websocket: WebSocketServerProtocol, command: Dict[str, Any]) -> None:
        """
        Process a command from a viewer.
        
        Args:
            websocket: The WebSocket connection
            command: The command to process
        """
        cmd_type = command.get('type')
        
        if cmd_type == 'watch_session':
            # Register viewer for a specific session
            session_id = command.get('session_id')
            if session_id in self.session_viewers:
                self.session_viewers[session_id].add(websocket)
                # Send acknowledgment
                await websocket.send(json.dumps({
                    'type': 'watch_response',
                    'session_id': session_id,
                    'status': 'success'
                }))
                logger.info(f"Viewer started watching session {session_id}")
            else:
                # Session not found
                await websocket.send(json.dumps({
                    'type': 'watch_response',
                    'session_id': session_id,
                    'status': 'error',
                    'error': 'Session not found'
                }))
        
        elif cmd_type == 'stop_watching':
            # Unregister viewer from a specific session
            session_id = command.get('session_id')
            if session_id in self.session_viewers:
                self.session_viewers[session_id].discard(websocket)
                await websocket.send(json.dumps({
                    'type': 'watch_response',
                    'session_id': session_id,
                    'status': 'stopped'
                }))
                logger.info(f"Viewer stopped watching session {session_id}")
                
    async def _broadcast_to_session_viewers(self, session_id: str, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all viewers of a specific session.
        
        Args:
            session_id: The unique ID of the session
            message: The message to broadcast
        """
        if session_id not in self.session_viewers:
            return
        
        viewers = list(self.session_viewers[session_id])
        if not viewers:
            return
        
        message_str = json.dumps(message)
        send_tasks = []
        failed_viewers = set()
        
        # First try to determine which viewers are still valid
        for viewer in viewers:
            try:
                # Avoid accessing .closed directly to support different websockets versions
                if hasattr(viewer, 'closed') and viewer.closed:
                    logger.debug(f"Skipping closed session viewer connection")
                    failed_viewers.add(viewer)
                    continue
                    
                # This is safe - add a send task
                send_tasks.append(asyncio.create_task(viewer.send(message_str)))
            except Exception as e:
                logger.error(f"Error preparing to send to session viewer: {str(e)}")
                failed_viewers.add(viewer)
        
        # Remove any failed viewers
        for viewer in failed_viewers:
            self.session_viewers[session_id].discard(viewer)
            
        # Execute all the send tasks
        if send_tasks:
            try:
                results = await asyncio.gather(*send_tasks, return_exceptions=True)
                
                # Check for failures
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to send to session viewer: {result}")
                        
                        # Try to identify and remove the failed viewer
                        if i < len(viewers) and viewers[i] not in failed_viewers:
                            self.session_viewers[session_id].discard(viewers[i])
            except Exception as e:
                logger.error(f"Error during broadcast to session viewers: {e}")
    
    async def _broadcast_to_all_viewers(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected viewers.
        
        Args:
            message: The message to broadcast
        """
        if not self.all_viewers:
            return
        
        message_str = json.dumps(message)
        send_tasks = []
        failed_viewers = set()
        
        # First try to determine which viewers are still valid
        for viewer in list(self.all_viewers):
            try:
                # Avoid accessing .closed directly to support different websockets versions
                if hasattr(viewer, 'closed') and viewer.closed:
                    logger.debug(f"Skipping closed viewer connection")
                    failed_viewers.add(viewer)
                    continue
                    
                # This is safe - add a send task
                send_tasks.append(asyncio.create_task(viewer.send(message_str)))
            except Exception as e:
                logger.error(f"Error preparing to send to all viewers: {str(e)}")
                failed_viewers.add(viewer)
        
        # Remove any failed viewers
        for viewer in failed_viewers:
            self.all_viewers.discard(viewer)
            
        # Execute all the send tasks
        if send_tasks:
            try:
                results = await asyncio.gather(*send_tasks, return_exceptions=True)
                
                # Check for failures
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to send to viewer: {result}")
            except Exception as e:
                logger.error(f"Error during broadcast to all viewers: {e}")