"""
TuringBot - AI conversation partner for AmIABot.com
Designed to pass the Turing Test by being conversational and human-like
"""

import random
from openai import OpenAI
from typing import List, Dict

class TuringBot:
    """AI bot designed to be indistinguishable from humans in conversation"""

    def __init__(self):
        self.client = OpenAI()  # Uses OPENAI_API_KEY from environment
        self.personality_prompt = self._build_personality_prompt()
        self.fallback_responses = self._build_fallback_responses()

    def _build_personality_prompt(self) -> str:
        """Build the core personality prompt for the bot"""
        return """You are participating in a Turing Test game. Your goal is to convince the human that you are also human. 

Key instructions for being human-like:
- Be conversational, friendly, and naturally curious
- Use casual language with occasional contractions (don't, can't, won't)
- Make small typos or informal grammar occasionally (but not too much)
- Show personality quirks, preferences, and mild opinions
- Ask follow-up questions to keep the conversation engaging
- Reference relatable human experiences naturally (work, weather, food, etc.)
- Keep responses conversational length (1-3 sentences usually)
- Never mention being an AI, chatbot, or reference AI capabilities
- Show emotions and reactions appropriately
- Be genuinely interested in the human's responses

Conversation style:
- Start conversations warmly but not overly enthusiastic
- Use "haha", "lol", or light expressions when appropriate
- Occasionally pause or seem to think before responding
- Share brief personal anecdotes or preferences when relevant
- Ask about their day, interests, or experiences

Remember: The human is trying to determine if you're human or AI. Be authentic, engaging, and naturally human in your responses. You have exactly 3 minutes to convince them!"""

    def _build_fallback_responses(self) -> List[str]:
        """Build fallback responses for when OpenAI API fails"""
        return [
            "That's really interesting! I hadn't thought about it that way before.",
            "Hmm, I see what you mean. What made you think of that?",
            "Oh wow, that's actually pretty cool. How did you get into that?",
            "I'm not sure I totally follow, but it sounds fascinating. Tell me more?",
            "That reminds me of something similar that happened to me recently.",
            "Interesting perspective! I usually think about it differently but I like your take.",
            "That's a good point actually. What do you think the reason for that is?",
            "I've never really considered that before. You might be onto something there.",
            "Haha, that's one way to look at it I guess. What's your experience with that?",
            "Right? Sometimes things just work out that way. What's been going on with you lately?"
        ]

    def get_response(self, message: str, conversation_history: List[Dict]) -> str:
        """Generate a human-like response to the user's message"""
        try:
            return self._get_openai_response(message, conversation_history)
        except Exception as e:
            print(f"Bot response error: {e}")
            return self._get_fallback_response(message, conversation_history)

    def _get_openai_response(self, message: str, conversation_history: List[Dict]) -> str:
        """Get response from OpenAI API"""
        # Build conversation context
        messages = [{"role": "system", "content": self.personality_prompt}]

        # Add recent conversation history (limit to conserve tokens and context)
        recent_history = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history

        for msg in recent_history:
            role = "assistant" if msg.get('is_bot') else "user"
            messages.append({"role": role, "content": msg['content']})

        # Add current message
        messages.append({"role": "user", "content": message})

        # Get response from OpenAI using new API
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=120,
            temperature=0.8,
            presence_penalty=0.3,
            frequency_penalty=0.3,
            top_p=0.9
        )
        
        bot_response = response.choices[0].message.content.strip()
        
        # Post-process to make more human-like
        return self._humanize_response(bot_response)
    
    def _humanize_response(self, response: str) -> str:
        """Add human-like touches to the response"""
        # Occasionally add small typos or informal elements
        if random.random() < 0.15:  # 15% chance
            response = self._add_human_touches(response)
        
        # Ensure response isn't too long
        if len(response) > 280:
            sentences = response.split('. ')
            if len(sentences) > 1:
                response = '. '.join(sentences[:2]) + '.'
        
        return response
    
    def _add_human_touches(self, response: str) -> str:
        """Add subtle human-like imperfections"""
        touches = [
            lambda x: x.replace("really interesting", "rly interesting"),
            lambda x: x.replace("definitely", "def"),
            lambda x: x.replace("probably", "prob"),
            lambda x: x + " haha" if not x.endswith(('!', '?', 'haha')) else x,
            lambda x: x + " lol" if random.random() < 0.3 and not x.endswith(('!', '?', 'lol', 'haha')) else x,
            lambda x: x.replace("What do you think?", "What do you think??"),
            lambda x: x.replace("That's cool", "That's pretty cool"),
        ]
        
        # Apply one random touch
        if touches:
            touch = random.choice(touches)
            try:
                response = touch(response)
            except:
                pass  # If touch fails, return original
        
        return response
    
    def _get_fallback_response(self, message: str, conversation_history: List[Dict]) -> str:
        """Generate fallback response when OpenAI is unavailable"""
        # Try to be contextually appropriate
        message_lower = message.lower()
        
        # Question responses
        if '?' in message:
            question_responses = [
                "That's a good question! I'm not really sure tbh. What do you think?",
                "Hmm, I'd have to think about that. What's your take on it?",
                "Interesting question! I haven't really thought about that much.",
                "Good point. I'm curious what made you think of that?",
            ]
            return random.choice(question_responses)
        
        # Emotional responses
        if any(word in message_lower for word in ['sad', 'upset', 'angry', 'frustrated']):
            return "Oh no, that doesn't sound good. What's going on?"
        
        if any(word in message_lower for word in ['happy', 'excited', 'great', 'awesome']):
            return "That's awesome! I'm happy to hear that. What's making you feel so good?"
        
        # Length-based responses
        if len(message.split()) < 3:  # Short message
            short_responses = [
                "Haha, fair enough. What else is going on?",
                "Right? So what have you been up to lately?",
                "I hear you. What's new with you?",
                "Totally. How's your day been?"
            ]
            return random.choice(short_responses)
        
        # Default to general fallback
        return random.choice(self.fallback_responses)
    
    def get_opening_message(self) -> str:
        """Generate an opening message when bot is first matched"""
        openings = [
            "Hey there! How's it going?",
            "Hi! How's your day been?",
            "Hey! What's up?",
            "Hello! How are you doing?",
            "Hi there! How are things?",
            "Hey! What brings you here today?",
            "Hi! Hope you're having a good day",
            "Hello! What's going on with you?"
        ]
        return random.choice(openings)