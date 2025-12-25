import time
import random as r
import requests
import os

f1 = open("sql_queries.md", "r")
f2 = open("queries.md", "r")
f3 = open("tag_queries.md", "r")
lines = f1.readlines() + f2.readlines() + f3.readlines()
queries = []

for line in lines:
    try:
        l = line.strip()
        if l[0].isdigit():
            _, _ , q = l.partition(" ")
            queries.append(q.strip())
    except IndexError:
        continue

user_identifiers = ["alex.martin@example.com",
                    "taylor.chen@example.com",
                    "jordan.ramirez@example.com"
                  ]

max_conversations = 5

BASE_URL = "https://localhost:5000"
CERT_DIR = os.path.join(os.path.dirname(__file__), "certs")
CLIENT_CERT = (os.path.join(CERT_DIR, "client.crt"), os.path.join(CERT_DIR, "client.key"))
CA_CERT = os.path.join(CERT_DIR, "ca.crt")


for i in range(5):
    req = requests.session()
    user_identifier = r.choice(user_identifiers)
    requests.delete(f"{BASE_URL}/api/sessions", json={"email": user_identifier}, cert=CLIENT_CERT, verify=CA_CERT)
    login_response = req.post(f"{BASE_URL}/api/login", json={'email': user_identifier}, cert=CLIENT_CERT, verify=CA_CERT)
    print("new session started....")
    mx = r.randint(1, max_conversations)
    for j in range(mx):
        q = r.choice(queries)
        payload = {'prompt': q}
        print(q)
        try:
            # Use the same session to carry cookies (session_id).
            response = req.post(f"{BASE_URL}/api/chat", json=payload, cert=CLIENT_CERT, verify=CA_CERT)
            reply = response.json()['reply']
            if isinstance(reply, list):
                reply = reply[0]['text']
            print(reply)
        except Exception as e:
            print(e)
            continue
    logout_response = req.post(f"{BASE_URL}/api/logout", cert=CLIENT_CERT, verify=CA_CERT)
    print("session ended....")
    print("--------------------------------")

queries = ['I want to place a new order of 2 Floor Mats','Instead of the 2 mats order i placed, i want 1 glow lamp']
for q in queries:
    req = requests.session()
    user_identifier = r.choice(user_identifiers)
    login_response = req.post(f"{BASE_URL}/api/login", json={'email': user_identifier}, cert=CLIENT_CERT, verify=CA_CERT)
    print("new session started....")
    payload = {'prompt': q}
    response = req.post(f"{BASE_URL}/api/chat", json=payload, cert=CLIENT_CERT, verify=CA_CERT)
    reply = response.json()['reply']
    print(reply)
    logout_response = req.post(f"{BASE_URL}/api/logout", cert=CLIENT_CERT, verify=CA_CERT)
    print("session ended....")
    print("--------------------------------")







