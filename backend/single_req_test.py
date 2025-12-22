import random as r
import requests


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

user_identifier = "alex.martin@example.com"

max_conversations = 1


req = requests.session()
login_response = req.post("http://localhost:5000/api/login", json={'email': user_identifier})
print(login_response.json())
print("new session started....")
#max_length = r.randint(1, max_conversations)
max_length = 1
for j in range(max_length):
    #q = r.choice(queries)
    q = 'Which customer has the phone number "+1-206-555-0155"'
    payload = {'prompt': q}
    print(q)
    # Use the same session so cookies (session_id) are included.
    response = req.post("http://localhost:5000/api/chat", json=payload)
    print(response.json())
logout_response = req.post("http://localhost:5000/api/logout")
print("session ended....")
print("--------------------------------")