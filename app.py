#!/usr/bin/env python3
"""
AmIABot.com MVP - Main Flask Application
A Modern Turing Test Game with real-time chat matching
"""

import os
import random
import fakeredis
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from eventlet import monkey_patch

# Load environment variables from .env file
load_dotenv()

# Import custom modules
from config import Config
from bot import TuringBot
from game_state import GameState

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Initialize FakeRedis for development (no Redis server needed)
try:
    storage_client = fakeredis.FakeRedis()
    storage_client.ping()
    print("FakeRedis connected successfully (development mode)")
    print("   Note: Using in-memory storage - data won't persist across restarts")
except ImportError:
    print("Warning: fakeredis not installed. Install with: pip install fakeredis")
    storage_client = None
except Exception as e:
    print(f"Warning: Storage not available: {e}")
    storage_client = None

# Initialize OpenAI client
openai_client = OpenAI()  # Uses OPENAI_API_KEY from environment

# Initialize game state and bot
game_state = GameState()
bot = TuringBot()

# Timer management
active_timers = {}


def schedule_timeout(delay: int, callback, *args):
    """Schedule a callback to run after delay seconds using SocketIO background task"""

    def wrapper():
        import time
        time.sleep(delay)
        callback(*args)

    task = socketio.start_background_task(wrapper)
    return task


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    user_id = request.sid
    print(f"=== CONNECT === User connected: {user_id}")
    print(f"Current queue size: {len(game_state.queue)}")
    print(f"Active sessions: {len(game_state.active_sessions)}")
    print(f"User agent: {request.environ.get('HTTP_USER_AGENT', 'unknown')}")
    emit('connected', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.sid
    print(f"=== DISCONNECT === User disconnected: {user_id}")
    print(f"Disconnect reason: {request.environ.get('disconnect_reason', 'unknown')}")

    # Remove from queue if present
    was_in_queue = game_state.remove_from_queue(user_id)
    if was_in_queue:
        print(f"Removed {user_id} from queue")

    # Handle active session
    session = game_state.get_user_session(user_id)
    if session:
        session_id = session['id']
        print(f"User {user_id} was in session {session_id} (bot: {session['is_bot']})")
        
        if session['is_bot']:
            # For bot sessions, just end the session
            print(f"User {user_id} disconnected from bot session {session_id}")
        else:
            # For human sessions, notify the other user
            other_user = session['user2'] if session['user1'] == user_id else session['user1']
            if other_user:
                print(f"Notifying {other_user} that {user_id} disconnected")
                socketio.emit('partner_disconnected', room=other_user)
                print(f"Sent partner_disconnected to {other_user}")

        # End the session
        game_state.end_session(session_id)
        print(f"Ended session {session_id}")
    else:
        print(f"User {user_id} was not in any active session")


@socketio.on('join_queue')
def handle_join_queue():
    user_id = request.sid
    print(f"User {user_id} joining queue")

    # Add to queue with timestamp
    success = game_state.add_to_queue(user_id)
    if success:
        emit('queue_joined', {'position': len(game_state.queue)})
    else:
        emit('error', {'message': 'Already in queue'})
        return

    # Schedule bot match after random delay (15-25 seconds) as fallback
    bot_delay = random.uniform(15, 25)
    print(f"User {user_id} will be matched with bot in {bot_delay:.1f}s if no human found")
    schedule_timeout(bot_delay, match_with_bot, user_id)

    # Wait minimum 5 seconds before attempting first match (reduced for testing)
    schedule_timeout(5, attempt_match, user_id, 0)


def attempt_match(user_id, attempt_count):
    """Try to match a user with a partner after minimum wait time"""
    with app.app_context():
        if not game_state.is_user_in_queue(user_id):
            print(f"User {user_id} not in queue, skipping match attempt")
            return  # User already matched or left

        attempt_count += 1
        print(f"Attempt {attempt_count} to match user {user_id}")
        print(f"Current queue: {[item['user_id'] for item in game_state.queue]}")

        # Try to find human partner who has also waited at least 5 seconds
        partner = game_state.get_queue_partner(exclude=user_id, min_wait_seconds=5)

        if partner and partner != user_id:
            # Human-to-human match
            print(f"Matching humans: {user_id} <-> {partner}")
            game_state.remove_from_queue(user_id)
            game_state.remove_from_queue(partner)
            session_id = game_state.create_session(user_id, partner, is_bot=False)

            # Notify both users individually (more reliable than rooms in background threads)
            print(f"Sending match_found to {user_id}")
            socketio.emit('match_found', {
                'session_id': session_id,
                'partner_type': 'human'
            }, to=user_id)

            print(f"Sending match_found to {partner}")
            socketio.emit('match_found', {
                'session_id': session_id,
                'partner_type': 'human'
            }, to=partner)

            print(f"Sent match_found to both {user_id} and {partner}")

            # Start conversation timer
            schedule_timeout(app.config['CONVERSATION_TIME'], end_conversation, session_id)
        else:
            # Keep checking for human partners every 2 seconds, but stop after 15 attempts (30 seconds)
            if attempt_count < 15:
                schedule_timeout(2, attempt_match, user_id, attempt_count)
            else:
                print(f"Max attempts reached for user {user_id}, bot match should trigger soon")


def match_with_bot(user_id):
    """Match user with bot after waiting period"""
    if not game_state.is_user_in_queue(user_id):
        print(f"User {user_id} not in queue, already matched or left")
        return  # User already matched or left

    print(f"Timeout reached - Matching {user_id} with bot")
    game_state.remove_from_queue(user_id)
    session_id = game_state.create_session(user_id, is_bot=True)

    print(f"Sending match_found (bot) to {user_id}")
    socketio.emit('match_found', {
        'session_id': session_id,
        'partner_type': 'unknown'  # Don't reveal it's a bot
    }, to=user_id)

    print(f"Sent match_found (bot) to {user_id}")

    # Send bot opening message
    def send_bot_opening():
        try:
            import time
            time.sleep(1.0)  # Brief delay before bot speaks
            
            session = game_state.get_session(session_id)
            if session and session['status'] == 'active':
                opening_message = bot.get_opening_message()
                print(f"Bot opening message: {opening_message}")
                
                # Add to session history
                bot_message_data = {
                    'content': opening_message,
                    'sender': 'bot',
                    'timestamp': datetime.now().isoformat(),
                    'is_bot': True
                }
                session['messages'].append(bot_message_data)
                
                # Send to user
                print(f"Attempting to send bot opening message to {user_id}")
                socketio.emit('new_message', {
                    'message': opening_message,
                    'sender': 'partner',
                    'timestamp': bot_message_data['timestamp']
                }, to=user_id)
                
                print(f"Bot opening message sent to {user_id}: {opening_message}")
                print(f"Bot opening data: {{'message': '{opening_message}', 'sender': 'partner', 'timestamp': '{bot_message_data['timestamp']}'}}")
            else:
                print(f"Session {session_id} not active for opening message")
        except Exception as ex:
            print(f"Error sending bot opening message: {ex}")
            import traceback
            traceback.print_exc()

    socketio.start_background_task(send_bot_opening)

    # Start conversation timer
    schedule_timeout(app.config['CONVERSATION_TIME'], end_conversation, session_id)


@socketio.on('send_message')
def handle_message(data):
    user_id = request.sid
    message = data.get('message', '').strip()
    
    print(f"=== MESSAGE RECEIVED === From: {user_id}")
    print(f"Message: '{message}'")
    print(f"Data received: {data}")

    if not message:
        print(f"Empty message from {user_id}")
        return

    session = game_state.get_user_session(user_id)
    if not session:
        print(f"ERROR: No session found for user {user_id}")
        print(f"Current user sessions: {game_state.user_sessions}")
        emit('error', {'message': 'No active session'})
        return
        
    print(f"Session found: {session['id']} (status: {session['status']}, bot: {session['is_bot']})")
    
    if session['status'] != 'active':
        print(f"ERROR: Session {session['id']} not active (status: {session['status']})")
        emit('error', {'message': 'Session not active'})
        return

    # Check if conversation time has expired
    elapsed = (datetime.now() - session['start_time']).total_seconds()
    if elapsed >= app.config['CONVERSATION_TIME']:
        emit('conversation_ended')
        return

    # Add message to session history
    message_data = {
        'content': message,
        'sender': user_id,
        'timestamp': datetime.now().isoformat(),
        'is_bot': False
    }
    session['messages'].append(message_data)
    print(f"Added message to session history. Total messages: {len(session['messages'])}")

    # Send to partner
    session_id = session['id']
    if session['is_bot']:
        # For bot sessions, only send to the user (bot will respond separately)
        print(f"Bot session - not sending to partner, bot will respond")
    else:
        # For human sessions, send to the other user
        other_user = session['user2'] if session['user1'] == user_id else session['user1']
        if other_user:
            print(f"Sending message to human partner: {other_user}")
            socketio.emit('new_message', {
                'message': message,
                'sender': 'partner',
                'timestamp': message_data['timestamp']
            }, to=other_user)
            print(f"Sent new_message to {other_user}")
        else:
            print(f"ERROR: No other user found in session {session_id}")

    # Confirm to sender
    print(f"Confirming message sent to sender {user_id}")
    emit('message_sent', {
        'message': message,
        'timestamp': message_data['timestamp']
    })
    print(f"Sent message_sent confirmation to {user_id}")

    # If partner is bot, generate response
    if session['is_bot']:
        print(f"Bot session detected for user {user_id}, generating response...")
        
        # Show typing indicator
        socketio.emit('partner_typing', {'typing': True}, to=user_id)

        def generate_and_send():
            try:
                print(f"Starting bot response generation for user {user_id}")
                
                # Generate bot response
                bot_response = bot.get_response(message, session['messages'])
                print(f"Bot generated response: {bot_response}")
                
                # Simple delay calculation
                base_delay = random.uniform(1.0, 2.0)
                char_delay = len(bot_response) / 10.0  # ~10 characters per second
                total_delay = min(max(base_delay + char_delay, 0.5), 4.0)
                
                print(f"Bot responding in {total_delay:.1f}s")
                
                # Wait for the calculated delay
                import time
                time.sleep(total_delay)

                # Check if session is still active
                current_session = game_state.get_session(session_id)
                if not current_session or current_session['status'] != 'active':
                    print(f"Session {session_id} no longer active, skipping bot response")
                    socketio.emit('partner_typing', {'typing': False}, to=user_id)
                    return

                # Stop typing indicator
                socketio.emit('partner_typing', {'typing': False}, to=user_id)

                # Add bot message to history
                bot_message_data = {
                    'content': bot_response,
                    'sender': 'bot',
                    'timestamp': datetime.now().isoformat(),
                    'is_bot': True
                }
                current_session['messages'].append(bot_message_data)

                # Send to user
                print(f"Attempting to send bot response to {user_id}")
                socketio.emit('new_message', {
                    'message': bot_response,
                    'sender': 'partner',
                    'timestamp': bot_message_data['timestamp']
                }, to=user_id)
                
                print(f"Bot response sent successfully to {user_id}: {bot_response}")
                print(f"Bot response data: {{'message': '{bot_response}', 'sender': 'partner', 'timestamp': '{bot_message_data['timestamp']}'}}")

            except Exception as ex:
                print(f"Error generating bot response: {ex}")
                import traceback
                traceback.print_exc()
                
                socketio.emit('partner_typing', {'typing': False}, to=user_id)
                
                # Send fallback response
                fallback = "Sorry, I'm having trouble thinking right now. What were you saying?"
                socketio.emit('new_message', {
                    'message': fallback,
                    'sender': 'partner',
                    'timestamp': datetime.now().isoformat()
                }, to=user_id)
                print(f"Sent fallback response to {user_id}")

        # Start the generation in a background task
        socketio.start_background_task(generate_and_send)
    else:
        # For human partners, relay typing indicator
        other_user = session['user2'] if session['user1'] == user_id else session['user1']
        if other_user:
            socketio.emit('partner_typing', {'typing': True}, to=other_user)
            # Auto-stop typing after message sent (already handled above)


@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator from human users"""
    user_id = request.sid
    is_typing = data.get('typing', False)

    session = game_state.get_user_session(user_id)
    if not session or session['status'] != 'active' or session['is_bot']:
        return

    # Relay to partner
    other_user = session['user2'] if session['user1'] == user_id else session['user1']
    if other_user:
        socketio.emit('partner_typing', {'typing': is_typing}, to=other_user)




def end_conversation(session_id: str):
    """End conversation and start decision phase"""
    session = game_state.get_session(session_id)
    if not session or session['status'] != 'active':
        return

    session['status'] = 'decision'

    # Notify participants that conversation has ended
    if session['is_bot']:
        socketio.emit('conversation_ended', {
            'message': 'Time\'s up! Now decide: was your partner a Bot or Human?'
        }, to=session['user1'])
    else:
        socketio.emit('conversation_ended', {
            'message': 'Time\'s up! Now decide: was your partner a Bot or Human?'
        }, to=session['user1'])
        socketio.emit('conversation_ended', {
            'message': 'Time\'s up! Now decide: was your partner a Bot or Human?'
        }, to=session['user2'])

    # Start decision timer
    schedule_timeout(app.config['DECISION_TIME'], force_decision, session_id)


@socketio.on('make_decision')
def handle_decision(data):
    user_id = request.sid
    decision = data.get('decision')  # 'bot' or 'human'

    if decision not in ['bot', 'human']:
        emit('error', {'message': 'Invalid decision'})
        return

    session = game_state.get_user_session(user_id)
    if not session or session['status'] != 'decision':
        emit('error', {'message': 'Not in decision phase'})
        return

    # Record decision
    session['decisions'][user_id] = decision

    # Check if all participants have decided
    expected_decisions = 2 if not session['is_bot'] else 1

    if len(session['decisions']) >= expected_decisions:
        reveal_results(session['id'])
    else:
        if session['is_bot']:
            # For bot sessions, immediately reveal results after user decides
            reveal_results(session['id'])
        else:
            emit('decision_recorded', {'message': 'Waiting for your partner to decide...'})


def force_decision(session_id: str):
    """Force decision phase to end and reveal results"""
    session = game_state.get_session(session_id)
    if not session or session['status'] != 'decision':
        return

    # For any users who haven't decided, record a random decision
    if not session['is_bot']:
        expected_users = [session['user1'], session['user2']]
    else:
        expected_users = [session['user1']]

    for user in expected_users:
        if user not in session['decisions']:
            session['decisions'][user] = random.choice(['bot', 'human'])

    reveal_results(session_id)


def reveal_results(session_id: str):
    """Reveal the results of the Turing test"""
    session = game_state.get_session(session_id)
    if not session:
        return

    # Determine the truth
    actual = 'bot' if session['is_bot'] else 'human'

    # Calculate results for each user
    results = {}
    for user_id, decision in session['decisions'].items():
        correct = decision == actual
        results[user_id] = {
            'decision': decision,
            'actual': actual,
            'correct': correct,
            'partner_type': actual
        }

    # Send results to each participant
    for user_id, result in results.items():
        socketio.emit('results', result, to=user_id)

    # Clean up session
    game_state.end_session(session_id)


# Web routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}


@app.route('/stats')
def get_stats():
    """Get current game statistics"""
    return game_state.get_stats()


@app.route('/debug')
def debug_info():
    """Debug endpoint to see current state"""
    return {
        'queue': game_state.queue,
        'active_sessions': {k: {
            'id': v['id'],
            'user1': v['user1'],
            'user2': v['user2'],
            'is_bot': v['is_bot'],
            'status': v['status'],
            'message_count': len(v['messages'])
        } for k, v in game_state.active_sessions.items()},
        'user_sessions': game_state.user_sessions
    }


@app.route('/test_bot')
def test_bot():
    """Test bot response generation"""
    try:
        test_message = "Hello, how are you?"
        test_history = []
        response = bot.get_response(test_message, test_history)
        return {
            'test_message': test_message,
            'bot_response': response,
            'bot_working': True
        }
    except Exception as exc:
        return {
            'error': str(exc),
            'bot_working': False
        }


# Run the application
if __name__ == '__main__':
    print("AmIABot MVP Server Starting...")
    print("\nSetup Checklist:")
    print("Install dependencies: pip install -r requirements.txt")
    print("Set OPENAI_API_KEY environment variable")
    print("Set SECRET_KEY (optional, has default)")
    print(f"\nServer will run on: http://0.0.0.0:{os.environ.get('PORT', 5000)}")
    print("Open in browser to start playing!")
    print("\nUsing FakeRedis (in-memory storage) - perfect for development!")
    print("   For production, configure a real Redis server in config.py")
    print("\n" + "=" * 50 + "\n")

    # Use port 5000 by default (Flask default)
    port = int(os.environ.get('PORT', 5000))

    monkey_patch()

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,  # Must be False in production
        allow_unsafe_werkzeug=True,
        # Additional options for better Windows compatibility
        use_reloader=False,
        log_output=True
    )