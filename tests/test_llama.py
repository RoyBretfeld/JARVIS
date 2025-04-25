import requests
import json

url = "http://localhost:8080/v1/chat/completions"
headers = {"Content-Type": "application/json"}
data = {
    "messages": [
        {
            "role": "system",
            "content": "Du bist JARVIS, ein hilfreicher KI-Assistent. Antworte kurz und präzise auf Deutsch."
        },
        {
            "role": "user",
            "content": "Sage Hallo und stelle dich vor!"
        }
    ]
}

response = requests.post(url, headers=headers, json=data)
print(json.dumps(response.json(), indent=2, ensure_ascii=False)) 