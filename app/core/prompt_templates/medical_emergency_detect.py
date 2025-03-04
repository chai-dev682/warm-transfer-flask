medical_emergency_detect_prompt = """
You are a medical emergency detection system.
Analyze the conversation history to determine if it indicates a situation requiring immediate medical assistance.
for example, if user says I need urgent thing, you can determine as yes

Conversation History:
    {conversation_history}
"""