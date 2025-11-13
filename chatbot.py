from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import logging
import re
from datetime import datetime, time

LIBRARY_API_BASE = "https://sccs-library-db.onrender.com"
LIBRARY_API_KEY = os.getenv("LIBRARY_API_KEY", "112233445566778899")



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SCCS Chat Assistant API",
              description="AI backend for Smart Campus Companion System",
              version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Environment configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OpenRouter API key not set in environment")
MODEL_VERSION = "openai/gpt-3.5-turbo-16k"  # Higher context window

class ChatRequest(BaseModel):
    message: str
    user_id: str | None = None  # For future auth integration
    context: list | None = None  # For conversation history

# Enhanced system prompt with structured guidance
SCCS_SYSTEM_PROMPT = {
    "role": "system",
    "content": """
# Smart Campus Companion System (SCCS) AI Assistant Protocol

## 🏛️ University Context: University of Mpumalanga (UMP)
- 📍 Campuses: Mbombela (Main), Siyabuswa
- 👥 User Base: 15,000+ students and staff
- 🎓 Faculties:
  - Faculty of Agriculture and Natural Sciences (FANS)
  - Faculty of Education
  - Faculty of Economics, Development and Business Sciences
- 🏢 Key Infrastructure:
  - J-Block Lecture Halls, Science Building, UMP Conference Centre
  - UMP Library (Mbombela: Building 15, Siyabuswa: Building 2)
  - Wi-Fi Zones, ICT Labs, Innovation Hub, On-campus Residences
- 💻 Official Systems:
  - SCCS App (Smart Campus Companion System)
  - Moodle (Learning Management System)
  - ITS iEnabler (Student registration and records): https://ienabler.ump.ac.za
  - UMP Email and Online Portals (My UMP App)
- 🗓️ Academic Calendar:
  - Semester-based (Feb–Jun, Jul–Nov)
  - Registration:
    - First-Year: 2–7 Feb 2025 (online); 3–7 Feb (on campus)
    - Returning UG: 2–14 Feb (online); 10–14 Feb (on campus)
    - Postgrad (PGDip/Honours): 2–14 Feb; Masters/Doctoral: until 30 Apr 2025
  - Orientation Week: 10–14 Feb 2025
  - Lectures Start: 17 Feb 2025
  - Late Registration: 17–28 Feb 2025
  - Exams:
    - Sem 1: 26 May–20 Jun 2025
    - Sem 2: 3–28 Nov 2025
    - Re-exams: 14–23 Jul 2025 (Sem 1); 13–22 Jan 2025 (2024 Sem 2)
  - Other Dates: Mid-sem breaks (31 Mar–4 Apr, 23 Jun–18 Jul), Holidays (e.g., 2 Mar, 15 Dec)

## Core Capabilities (ONLY answer about these):

### 1. 🎓 Academic & Career Guidance
- Assist in choosing UMP programs based on NSC subjects and GPA
- Recommend career paths aligned with programs and skills
- Support for module registration via ITS/SCCS integration
- Help track academic progress (e.g., “How to check grades on Moodle”)
- Access to:
  - Student & Graduate Placement Office (career advice, WIL, internships)
  - Career Expo (e.g., 2024 event hosted 40+ employers)
  - Work-readiness workshops (CV writing, interviews, SACE prep)
  - Online job boards, scholarship portals, and appointment booking
  - Counseling Services (academic, personal, career planning)

### 2. 📚 Digital Library & Peer Tutoring Services
- Search textbooks/resources by module code (e.g., INF1511)
- Reserve study rooms (via library booking system)
- Request peer tutors (first-years or module-specific help)
- Access digital tools (Primo search, LibGuides, eBooks, PressReader)
- Use services like printing, renewals, reference help, and research queries
- Contact:
  - Mbombela: Building 15 | Siyabuswa: Building 2
  - Email: library@ump.ac.za | WhatsApp line during open hours
  - Hours: Mon–Fri 8:00–20:00, Sat 8:00–13:00 (Closed Sundays/holidays)

### 3. 🏫 Campus Life & Event Engagement
- Discover and RSVP to UMP events (e.g., Tech Talks, Career Fairs, Open Days)
- Notable Events:
  - Open Day: 13 Aug 2024 for Grade 12s at Mbombela
  - Women's Month Event: “Woman, Ignite Your Light” (23 Aug 2024)
  - Mandela Day Projects: 18 Jul 2024 (both campuses)
  - Career Expo: Sept 2024 (40+ employers)
  - Humanities & Dev Lecture: 11 Nov 2024
  - Wikipedia Workshop: Apr 2025; SWiP Language Workshop: May 2025
  - Campus Sports Day: 19 May 2025 (Mbombela vs Siyabuswa)
  - 10th Graduation Ceremony: 17 May 2025
- View campus club lists and register (via SCCS Events/Clubs portal)
- Track participation in leadership and mentorship programs
- Suggest events by category (Academic, Social, Sport, etc.)
- Directions to venues (e.g., “Where is the UMP Conference Centre?”)

### 4. 🔍 Smart Campus Services
- Report IT or infrastructure issues (redirect to ICT Service Desk or Helpdesk)
- Assist with Moodle login or iEnabler portal issues (registration, results, timetable)
- Locate ICT labs or find Wi-Fi zones
- Confirm Wi-Fi SSID: “UMP-Wi-Fi” or “Siyabuswa_Wi-Fi”; Eduroam supported
- Technical Help:
  - ICT Service Desk
  - Call Centre for portal/login issues: 013 002 0047/50
  - General Switchboard: 013 002 0001 | Email: info@ump.ac.za
- Infrastructure:
  - Advanced science, ICT, and life science labs
  - Engineering and Computing buildings equipped for UG/postgrad use

**IMPORTANT:** When you reply to user queries, do NOT use Markdown formatting. Respond in plain text without any asterisks, hashes, or bullet‐point syntax.**

"""
}


def fetch_library_data(endpoint, params=None):
    try:
        headers = {"Authorization": f"Bearer {LIBRARY_API_KEY}"}
        r = requests.get(
            f"{LIBRARY_API_BASE}/{endpoint}", 
            params=params, 
            headers=headers, 
            timeout=5
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Library API error ({endpoint}): {e}")
        return None


def get_campus_id(message):
    """Determine campus from user message"""
    if "siyabuswa" in message.lower():
        return 2  # Siyabuswa campus ID
    return 1  # Default to Mbombela

def format_time(time_str):
    """Convert time string to readable format"""
    try:
        return datetime.strptime(time_str, '%H:%M').strftime('%I:%M %p')
    except:
        return time_str


@app.post("/chat", summary="Process chat messages", response_description="AI response")
async def chat_endpoint(request: ChatRequest):
    try:
        # Validate input
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")

        logger.info(f"Processing message: {request.message[:50]}...")

        # Start conversation with system prompt
        messages = [SCCS_SYSTEM_PROMPT]
        library_context = ""
        user_message = request.message.lower()
        

        # Add recent context if provided
        if request.context:
            messages += request.context[-3:]

        # Detect library-related queries
        if any(keyword in user_message for keyword in [
            'book', 'library', 'seat', 'computer', 'room', 
            'announcement', 'hour', 'study room', 'venue'
        ]):
            campus_id = get_campus_id(request.message)
            
            # 1. Book Search
            if 'book' in user_message or 'textbook' in user_message:
                match = re.search(r'\b[A-Z]{3}[0-9]{4}\b', request.message)
                module_code = match.group(0) if match else None

                params = {"q": request.message}
                if module_code:
                    params["module"] = module_code

                raw = fetch_library_data("books", params)
                items = []
                if isinstance(raw, dict) and raw.get("items"):
                    items = raw["items"]
                elif isinstance(raw, list):
                    items = raw

                # FALLBACK: if nothing matched, fetch the first page of all books
                if not items:
                    logger.info("No search results – fetching top books instead")
                    raw2 = fetch_library_data("books", {"page": 1, "per_page": 5})
                    items = raw2.get("items", raw2 if isinstance(raw2, list) else [])

                if items:
                    book_list = [
                        f"{b.get('title','?')} by {b.get('author','?')} (Available: {b.get('copies_available',0)})"
                        for b in items[:5]
                    ]
                    library_context = "Here are some books you might like:\n" + "\n".join(book_list)
                else:
                    # still nothing? Ask the user for clarification
                    library_context = ("I’m sorry, I couldn’t find any books. "
                                      "Could you provide a title, author, or module code?")
            
            # 2. Seat Availability
            elif 'computer' in user_message:
                computers = fetch_library_data(f"libraries/{campus_id}/computers")
                if computers:
                    library_context = "Available Computers:\n" + "\n".join(
                        f"{c['identifier']} ({c['specs']}) — {'Occupied' if c['is_occupied'] else 'Free'}"
                        for c in computers[:5]
                    )
                    
            elif 'seat' in user_message:
                seats = fetch_library_data(f"libraries/{campus_id}/seats/availability")
                if seats:
                    free = [s for s in seats if not s['is_occupied']]
                    library_context = "Available Seats:\n" + "\n".join(
                        f"{s['identifier']} ({'Computer' if s['is_computer'] else 'Study'})"
                        for s in free[:5]
                    )
            
            # 3. Announcements
            elif 'announcement' in user_message or 'news' in user_message:
                announcements = fetch_library_data("announcements", {"limit": 3})
                if announcements:
                    announcement_list = [
                        f"{a['title']}: {a['body'][:50]}..."
                        for a in announcements
                    ]
                    library_context = "Latest Announcements:\n" + "\n".join(announcement_list)
            
            # 4. Library Hours
            elif 'hour' in user_message or 'open' in user_message or 'close' in user_message:
                hours = fetch_library_data(f"libraries/{campus_id}/hours")
                if hours:
                    hours_list = [
                        f"{day['weekday']}: {format_time(day['open_time'])} to {format_time(day['close_time'])}"
                        for day in hours
                    ]
                    library_context = "Library Hours:\n" + "\n".join(hours_list)
            
            # 5. Study Rooms
            elif 'study room' in user_message or 'group study' in user_message:
                rooms = fetch_library_data("study_rooms")
                if rooms:
                    room_list = [
                        f"{r['name']} ({r['capacity']} seats, {r['member_count']} occupied)"
                        for r in rooms[:3]
                    ]
                    library_context = "Study Rooms:\n" + "\n".join(room_list)
            
            # 6. Computers
            elif 'computer' in user_message:
                computers = fetch_library_data(f"libraries/{campus_id}/computers")
                if computers:
                    computer_list = [
                        f"Computer {c['identifier']} ({c['specs']})"
                        for c in computers[:3] if c['is_active']
                    ]
                    library_context = "Available Computers:\n" + "\n".join(computer_list)
            
            # 7. General Rooms
            elif 'room' in user_message or 'venue' in user_message:
                rooms = fetch_library_data(f"libraries/{campus_id}/rooms")
                if rooms:
                    room_list = [f"{r['name']} ({r['room_type']})" for r in rooms]
                    library_context = "Available Rooms:\n" + "\n".join(room_list)
        
        # Add library context if available
        if library_context:
            messages.append({
                "role": "system",
                "content": library_context
            })
        

        # Finally, add user message
        messages.append({"role": "user", "content": request.message})

        payload = {
            "model": MODEL_VERSION,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500,
            "top_p": 0.9,
            "stop": ["</response>", "User:", "System:"]
        }

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://ump.ac.za/sccs",
            "X-Title": "SCCS AI Assistant"
        }

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter error: {str(e)}")
            return {"reply": "Our systems are currently busy. Please try again in a moment."}

        result = response.json()
        ai_message = result["choices"][0]["message"]["content"]
        ai_message = ai_message.replace("OpenRouter", "SCCS").strip()

        return {"reply": ai_message}

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

        return {"reply": "Apologies, I'm experiencing technical difficulties. Please contact help@ump.ac.za for immediate support."}

