import requests

url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

payload = {
    "model": "glm-4.5-flash",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 1,
    "max_tokens": 65536,
    "stream": False,
    "thinking": {"type": "enabled"},
    "do_sample": True,
    "top_p": 0.95,
    "tool_stream": False,
    "response_format": {"type": "text"},
}
headers = {
    "Authorization": "Bearer 6d1847d3044742498efb0c63b37bc904.fstXIOTUYIKZI4oa",
    # "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)
