"""
Game state management for AmIABot.com
Handles user queues, active sessions, and matchmaking
"""

import uuid
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

class GameState:
    """Thread-safe game state management"""
    
    def __init__(self):
        self.queue: List[str] = []
        self.active_sessions: Dict[str, dict] = {}
        self.user_sessions: Dict[str, str] = {}  # socket_id -> session_id
        self.lock = Lock()
    
    def add_to_queue(self, user_id: str) -> bool:
        """Add user to matchmaking queue"""
        with self.lock:
            # Check if user is already in queue
            for item in self.queue:
                if item['user_id'] == user_id:
                    return False
            
            # Store user with timestamp
            self.queue.append({'user_id': user_id, 'joined_at': datetime.now()})
            print(f"Added {user_id} to queue. Queue size: {len(self.queue)}")
            return True

    def remove_from_queue(self, user_id: str) -> bool:
        """Remove user from matchmaking queue"""
        with self.lock:
            for item in self.queue:
                if item['user_id'] == user_id:
                    self.queue.remove(item)
                    print(f"Removed {user_id} from queue. Queue size: {len(self.queue)}")
                    return True
            return False

    def is_user_in_queue(self, user_id: str) -> bool:
        """Check if user is in queue"""
        with self.lock:
            for item in self.queue:
                if item['user_id'] == user_id:
                    return True
            return False

    def get_queue_partner(self, exclude: str = None, min_wait_seconds: int = 0) -> Optional[str]:
        """Get next available partner from queue, excluding specified user"""
        with self.lock:
            now = datetime.now()
            # Find first user in queue that isn't the excluded user and has waited long enough
            for item in self.queue:
                user_id = item['user_id']
                joined_at = item['joined_at']
                wait_time = (now - joined_at).total_seconds()

                if user_id != exclude and wait_time >= min_wait_seconds:
                    print(f"Found queue partner: {user_id} (waited {wait_time:.1f}s). Queue size: {len(self.queue)}")
                    return user_id
        return None
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        with self.lock:
            return len(self.queue)
    
    def create_session(self, user1_id: str, user2_id: str = None, is_bot: bool = False) -> str:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        
        with self.lock:
            session_data = {
                'id': session_id,
                'user1': user1_id,
                'user2': user2_id,
                'is_bot': is_bot,
                'start_time': datetime.now(),
                'end_time': None,
                'messages': [],
                'decisions': {},
                'status': 'active'  # active, decision, ended
            }
            
            self.active_sessions[session_id] = session_data
            self.user_sessions[user1_id] = session_id
            
            if user2_id:
                self.user_sessions[user2_id] = session_id
            
            session_type = "bot" if is_bot else "human"
            print(f"Created {session_type} session {session_id} for users: {user1_id}, {user2_id}")
            
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session by ID"""
        with self.lock:
            return self.active_sessions.get(session_id)
    
    def get_user_session(self, user_id: str) -> Optional[dict]:
        """Get active session for a user"""
        with self.lock:
            session_id = self.user_sessions.get(user_id)
            if session_id:
                return self.active_sessions.get(session_id)
        return None
    
    def update_session_status(self, session_id: str, status: str) -> bool:
        """Update session status (active, decision, ended)"""
        with self.lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]['status'] = status
                print(f"Updated session {session_id} status to: {status}")
                return True
        return False
    
    def add_message_to_session(self, session_id: str, message_data: dict) -> bool:
        """Add message to session history"""
        with self.lock:
            session = self.active_sessions.get(session_id)
            if session:
                session['messages'].append(message_data)
                
                # Limit message history to prevent memory bloat
                if len(session['messages']) > 100:  # Keep last 100 messages
                    session['messages'] = session['messages'][-100:]
                
                return True
        return False
    
    def add_decision_to_session(self, session_id: str, user_id: str, decision: str) -> bool:
        """Record user's bot/human decision"""
        with self.lock:
            session = self.active_sessions.get(session_id)
            if session:
                session['decisions'][user_id] = decision
                print(f"User {user_id} decided: {decision} for session {session_id}")
                return True
        return False
    
    def get_session_decisions(self, session_id: str) -> dict:
        """Get all decisions for a session"""
        with self.lock:
            session = self.active_sessions.get(session_id)
            if session:
                return session['decisions'].copy()
        return {}
    
    def end_session(self, session_id: str) -> bool:
        """End a session and clean up resources"""
        with self.lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False
            
            # Update session status
            session['end_time'] = datetime.now()
            session['status'] = 'ended'
            
            # Clean up user session mappings
            user1 = session.get('user1')
            user2 = session.get('user2')
            
            if user1 and user1 in self.user_sessions:
                del self.user_sessions[user1]
            
            if user2 and user2 in self.user_sessions:
                del self.user_sessions[user2]
            
            print(f"Ended session {session_id}")
            
            # Optional: Remove session after some time to free memory
            # For MVP, we keep ended sessions for potential analytics
            
        return True
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old sessions to prevent memory leaks"""
        from datetime import timedelta
        
        expired_sessions = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self.lock:
            for session_id, session in self.active_sessions.items():
                if session['start_time'] < cutoff_time:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.active_sessions[session_id]
                print(f"Cleaned up expired session: {session_id}")
        
        return len(expired_sessions)
    
    def get_stats(self) -> dict:
        """Get current system statistics"""
        with self.lock:
            active_sessions = sum(1 for s in self.active_sessions.values() if s['status'] == 'active')
            decision_sessions = sum(1 for s in self.active_sessions.values() if s['status'] == 'decision')
            bot_sessions = sum(1 for s in self.active_sessions.values() if s['is_bot'])
            human_sessions = sum(1 for s in self.active_sessions.values() if not s['is_bot'])
            
            return {
                'queue_size': len(self.queue),
                'total_sessions': len(self.active_sessions),
                'active_sessions': active_sessions,
                'decision_sessions': decision_sessions,
                'bot_sessions': bot_sessions,
                'human_sessions': human_sessions,
                'connected_users': len(self.user_sessions)
            }