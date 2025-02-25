from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from twilio.twiml.voice_response import VoiceResponse, Connect
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
import json
import traceback
from warm_transfer_flask import app as flask_app
from warm_transfer_flask.config import config_classes

from . import token, call, twiml_generator
from .models import ActiveCall
from .twilio_audio_interface import TwilioAudioInterface

AGENT_WAIT_URL = 'http://twimlets.com/holdmusic?Bucket=com.twilio.music.classical'

app = FastAPI()
templates = Jinja2Templates(directory="warm_transfer_flask/templates")

def get_eleven_labs_client():
    """Initialize ElevenLabs client with configuration"""
    if not flask_app.config.get('ELEVENLABS_API_KEY'):
        # Load config if not already loaded
        env = flask_app.config.get("ENV", "production")
        flask_app.config.from_object(config_classes[env])
    
    return ElevenLabs(api_key=flask_app.config['ELEVENLABS_API_KEY'])

# Move the client initialization to a function that's called when needed
eleven_labs_client = None

def get_client():
    global eleven_labs_client
    if eleven_labs_client is None:
        eleven_labs_client = get_eleven_labs_client()
    return eleven_labs_client

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# @app.post("/conference/connect/client")
# async def connect_client(request: Request):
#     form = await request.form()
#     conference_id = form['CallSid']
#     connect_agent_url = str(request.url_for(
#         'connect_agent', agent_id='agent1', conference_id=conference_id
#     ))
#     call.call_agent('agent1', connect_agent_url)
#     ActiveCall.create('0', conference_id)
#     return Response(
#         content=twiml_generator.generate_connect_conference(
#             conference_id, str(request.url_for('wait')), False, True
#         ),
#         media_type="application/xml"
#     )

# @app.api_route("/twilio/inbound_call", methods=["GET", "POST"])
@app.api_route("/conference/connect/client", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response."""
    response = VoiceResponse()
    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream-eleven")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.post("/{agent_id}/token")
async def generate_token_endpoint(agent_id: str):
    return JSONResponse({
        "token": token.generate(agent_id),
        "agentId": agent_id
    })

@app.post("/conference/{agent_id}/call")
async def call_agent_endpoint(agent_id: str):
    conference_id = ActiveCall.conference_id_for(agent_id)
    connect_agent_url = str(app.url_path_for(
        'connect_agent', agent_id='agent2', conference_id=conference_id
    ))
    return Response(content=call.call_agent('agent2', connect_agent_url))

@app.post("/conference/wait")
async def wait():
    return Response(
        content=twiml_generator.generate_wait(),
        media_type="application/xml"
    )

@app.route("/conference/{conference_id}/connect/{agent_id}", methods=["POST", "GET"])
async def connect_agent(conference_id: str, agent_id: str):
    exit_on_end = 'agent2' == agent_id
    return Response(
        content=twiml_generator.generate_connect_conference(
            conference_id, AGENT_WAIT_URL, True, exit_on_end
        ),
        media_type="application/xml"
    )

@app.websocket("/media-stream-eleven")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection established")
    audio_interface = TwilioAudioInterface(websocket)
    conversation = None
    try:
        conversation = Conversation(
            client=get_client(),
            agent_id=flask_app.config['ELEVENLABS_AGENT_ID'],
            requires_auth=False,
            audio_interface=audio_interface,
            callback_agent_response=lambda text: print(f"Agent said: {text}"),
            callback_user_transcript=lambda text: print(f"User said: {text}"),
        )
        conversation.start_session()
        print("Conversation session started")
        async for message in websocket.iter_text():
            if not message:
                continue
            try:
                data = json.loads(message)
                await audio_interface.handle_twilio_message(data)
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                traceback.print_exc()
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    finally:
        if conversation:
            print("Ending conversation session...")
            conversation.end_session()
            conversation.wait_for_session_end()