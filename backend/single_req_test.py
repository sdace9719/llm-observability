import random as r
import requests
import os


f = open("tag_queries.md", "r")

lines = f.readlines()
queries = []

for line in lines:
    try:
        l = line.strip()
        if l[0].isdigit():
            _, _ , q = l.partition(" ")
            queries.append(q.strip())
    except IndexError:
        continue

user_identifier = "taylor.chen@example.com"

BASE_URL = "https://localhost:5000"
CERT_DIR = os.path.join(os.path.dirname(__file__), "certs")
CLIENT_CERT = (os.path.join(CERT_DIR, "client.crt"), os.path.join(CERT_DIR, "client.key"))
CA_CERT = os.path.join(CERT_DIR, "ca.crt")

max_conversations = 1


req = requests.session()
login_response = req.post(f"{BASE_URL}/api/login", json={'email': user_identifier}, cert=CLIENT_CERT, verify=CA_CERT)
print(login_response.json())
print("new session started....")
#max_length = r.randint(1, max_conversations)
#Instead of the 2 mats order i placed, i want 1 glow lamp.
max_length = 1
for j in range(max_length):
    #q = r.choice(queries)
    #q = 'I want to place a new order of 2 Floor Mats'
    q = 'Instead of the 2 mats order i placed, i want 1 glow lamp.'
    payload = {'prompt': q}
    print(q)
    # Use the same session so cookies (session_id) are included.
    response = req.post(f"{BASE_URL}/api/chat", json=payload, cert=CLIENT_CERT, verify=CA_CERT)
    print(response.json()['reply'])
logout_response = req.post(f"{BASE_URL}/api/logout", cert=CLIENT_CERT, verify=CA_CERT)
print("session ended....")
print("--------------------------------")