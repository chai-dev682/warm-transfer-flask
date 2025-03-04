import json

function_list = [
    {
        "type": "function",
        "function": {
            "name": "detect_medical_emergency",
            "description": "Determines if text indicates a medical emergency requiring immediate assistance",
            "parameters": {
                "type": "object",
                "properties": {
                    "is_emergency": {
                        "type": "boolean",
                        "description": "True if the text indicates a medical emergency requiring immediate assistance"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Explanation of why this is or is not considered a medical emergency"
                    }
                },
                "required": ["is_emergency", "reason"]
            }
        }
    }
]


function_tool = json.loads(json.dumps(function_list))