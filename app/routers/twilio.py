from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from twilio.rest import Client
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai import ChatOpenAI
import json
import traceback

from app.services.twilio_audio_interface import TwilioAudioInterface
from app.core.function_templates.functions import function_tool
from app.core.prompt_templates.medical_emergency_detect import medical_emergency_detect_prompt
from app.core import settings, ModelType

router = APIRouter()

# Move the client initialization to a function that's called when needed
eleven_labs_client = None

model = ChatOpenAI(
    model=ModelType.gpt4o,
    openai_api_key=settings.OPENAI_API_KEY
)

def get_client():
    global eleven_labs_client
    if eleven_labs_client is None:
        eleven_labs_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    return eleven_labs_client

def format_conversation_history(messages: ChatMessageHistory) -> str:
    return "\n".join([f"{msg.type}: {msg.content}" for msg in messages.messages])

def extract_function_params(prompt, function):
    function_name = function[0]["function"]["name"]
    model_ = model.bind_tools(function, tool_choice=function_name)
    messages = [SystemMessage(prompt)]
    tool_call = model_.invoke(messages).tool_calls
    prop = tool_call[0]['args']

    return prop

def create_agent_response_callback(conversation_history):
    return lambda text: (
        print(f"Agent said: {text}"),
        conversation_history.add_ai_message(AIMessage(content=text))
    )

def create_user_transcript_callback(conversation_history):
    return lambda text: (
        print(f"User said: {text}"),
        conversation_history.add_user_message(HumanMessage(content=text))
    )

def requires_medical_assistance(conversation_history) -> bool:
    """
    Analyze text using OpenAI function calling to determine if urgent medical assistance is needed.
    
    Args:
        conversation_history: The conversation history to analyze
        
    Returns:
        bool: True if medical assistance is needed, False otherwise
    """
    try:
        prop = extract_function_params(prompt=medical_emergency_detect_prompt.format(conversation_history=format_conversation_history(conversation_history)), function=function_tool)        
        # Log the analysis
        print(f"Medical emergency analysis: {prop['is_emergency']} - {prop['reason']}")
        
        return prop
        
    except Exception as e:
        print(f"Error in medical emergency detection: {str(e)}")
        traceback.print_exc()
                
        return False

async def transfer_to_medical_services(websocket: WebSocket, conversation_history: ChatMessageHistory):
    """
    Transfer the current call to medical services using Twilio's API.
    """
    try:
        # Get the call SID from the websocket
        call_sid = getattr(websocket, "call_sid", None)
        if not call_sid:
            print("Error: No call SID available for transfer")
            return
            
        # Inform the caller
        await websocket.send_json({
            "event": "message",
            "message": "We've detected a potential medical emergency. Transferring you to medical services. Please stay on the line."
        })
        
        # Create a Twilio client
        client = Client(
            settings.TWILIO_API_KEY,
            settings.TWILIO_API_SECRET,
            settings.TWILIO_ACCOUNT_SID
        )
        
        # Create a conference for the transfer
        conference_name = f"medical_emergency_{call_sid}"
        
        # Update the call to join the conference
        client.calls(call_sid).update(
            twiml=f'<Response><Dial><Conference>{conference_name}</Conference></Dial></Response>'
        )
        
        # Get the emergency reason to send to medical services
        emergency_reason = getattr(websocket, "emergency_text", "Potential medical emergency")
        
        # Call medical services with TwiML that first plays a message before joining the conference
        medical_service_number = '+19492728928'  # Configure this in your settings
        
        # Create TwiML that first plays a message explaining the situation before joining the conference
        twiml = f"""
        <Response>
            <Say>Attention medical services. This is an automated transfer from an AI assistant that has detected a potential medical emergency.</Say>
            <Pause length="1"/>
            <Say>The caller reported: {emergency_reason}</Say>
            <Pause length="1"/>
            <Say>You will now be connected to the caller. Please provide assistance.</Say>
            <Dial>
                <Conference>{conference_name}</Conference>
            </Dial>
        </Response>
        """
        
        client.calls.create(
            to=medical_service_number,
            from_=settings.TWILIO_NUMBER,
            twiml=twiml
        )
        
        print(f"Call transferred to medical services. Conference: {conference_name}")
        
    except Exception as e:
        print(f"Error transferring call to medical services: {str(e)}")
        traceback.print_exc()


@router.api_route("/conference/connect/client", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response."""
    # Extract the Call SID from the request
    # form_data = await request.form()
    
    response = VoiceResponse()
    host = request.url.hostname
    connect = Connect()
    
    # Pass the Call SID as a query parameter to the WebSocket URL
    connect.stream(url=f"wss://{host}/media-stream-eleven")
    
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

@router.websocket("/media-stream-eleven")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connection established")
    
    audio_interface = TwilioAudioInterface(websocket)
    conversation = None
    conversation_history = ChatMessageHistory()
    
    # Create a simpler callback that just checks and logs
    def create_medical_aware_agent_response_callback(conversation_history, websocket):
        original_callback = create_agent_response_callback(conversation_history)
        
        def enhanced_callback(text):
            # Call the original callback
            original_callback(text)
            
            # Check if medical assistance is required
            prop = requires_medical_assistance(conversation_history)
            if prop["is_emergency"]:
                print(f"MEDICAL EMERGENCY DETECTED: {prop['reason']}")
                # Set a flag that we'll check in the main WebSocket loop
                websocket.medical_emergency = True
                websocket.emergency_text = prop["reason"]
        
        return enhanced_callback
    
    try:
        # Store the stream SID when it becomes available
        websocket.stream_sid = None
        websocket.medical_emergency = False
        websocket.emergency_text = None
        
        conversation = Conversation(
            client=get_client(),
            agent_id=settings.ELEVENLABS_AGENT_ID,
            requires_auth=False,
            audio_interface=audio_interface,
            callback_agent_response=create_medical_aware_agent_response_callback(conversation_history, websocket),
            callback_user_transcript=create_user_transcript_callback(conversation_history),
        )
        conversation.start_session()
        print("Conversation session started")
        
        async for message in websocket.iter_text():
            if not message:
                continue
            try:
                data = json.loads(message)
                
                # Store the stream SID when it's received in the start event
                if data.get("event") == "start" and "start" in data:
                    websocket.stream_sid = data["start"].get("streamSid")
                    websocket.call_sid = data["start"].get("callSid")
                    print(f"Stored stream SID: {websocket.stream_sid}")
                    print(f"Stored call SID: {websocket.call_sid}")
                await audio_interface.handle_twilio_message(data)
                
                # Check if we need to handle a medical emergency
                if getattr(websocket, "medical_emergency", False):
                    websocket.medical_emergency = False  # Reset the flag
                    await transfer_to_medical_services(websocket, conversation_history)
                    
            except Exception as e:
                print(f"Error processing message: {str(e)}")
                traceback.print_exc()
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    finally:
        if conversation:
            conversation.end_session()
