import ssl
import email
from uuid import uuid4
from tinydb import TinyDB, Query
from tinydb.queries import where
from fastapi import FastAPI, Header
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.status import (HTTP_400_BAD_REQUEST,
                              HTTP_500_INTERNAL_SERVER_ERROR,
                              HTTP_401_UNAUTHORIZED)
from pydantic import BaseModel
from imapclient import IMAPClient, exceptions

class Login(BaseModel):
    username: str
    password: str


app = FastAPI()

origins = [
    "localhost",
    "https://mail.hipsters.live"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def connect() -> IMAPClient:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    m = IMAPClient("mail.dr6.com.br", ssl_context=ssl_context)
    return m

def connect_imap(token: str) -> IMAPClient:
    db = TinyDB('session.json')
    Ident = Query()
    user = db.search(Ident.token == token)

    if len(user) == 1:
        m = connect()
        try:
            m.login(user[0]['username'], user[0]['password'])
            return m
        except exceptions.LoginError:
            return None
    return None


@app.get("/")
async def root():
    m = connect()
    s = m.noop()
    return {"message": s}

@app.get("/select/{mailbox}/{msgid}")
async def message(mailbox: str, msgid: int, response: Response, token: str = Header(None)):
    m = connect_imap(token)
    if not m:
        response.status_code = HTTP_401_UNAUTHORIZED
        return None

    m.select_folder(mailbox)
    f = m.fetch(msgid, ['RFC822'])
    message = email.message_from_bytes(f[msgid][b'RFC822'])

    body = ""
    if message.is_multipart():
        for payload in message.get_payload():
            body += payload.get_payload()
    else:
        body = message.get_payload()
    return {"header": message, "payload": body}

@app.get("/select/{mailbox}")
async def select(mailbox: str, response: Response, token: str = Header(None)):
    m = connect_imap(token)
    if not m:
        response.status_code = HTTP_401_UNAUTHORIZED
        return None

    m.select_folder(mailbox)
    messages = m.search()
    lista = []
    for mid, data in m.fetch(messages, ['FLAGS', 'ENVELOPE']).items():
        envelope = data[b'ENVELOPE']
        lista.append(
            {
                "id": mid,
                "subject": envelope.subject.decode(),
                "date": envelope.date,
                "sender": envelope.sender,
                "senders_emails": ";".join([f'{s[2].decode()}@{s[3].decode()}' for s in envelope.sender]),
                "to": envelope.to,
                "bcc": envelope.bcc,
                "cc": envelope.cc,
                "in_reply_to": envelope.in_reply_to,
                "reply_to": envelope.reply_to,
                "flags": data[b'FLAGS'],
                "is_seen": b'\\Seen' in data[b'FLAGS']
            })
    return sorted(lista, key = lambda i: i['date'], reverse=True) 

@app.get("/mailboxes/")
async def mailboxes(response: Response, token: str = Header(None)):
    m = connect_imap(token)

    if not m:
        response.status_code = HTTP_401_UNAUTHORIZED
        return None

    folders = m.list_folders()
    return [folder[-1:][0] for folder in folders]

@app.post("/login/")
async def login(credentials: Login, response: Response):
    db = TinyDB('session.json')
    m = connect()
    res: str

    try:
        res = m.login(credentials.username, credentials.password)
        key = str(uuid4().hex)
        db.remove(where('username') == credentials.username)
        db.insert({
            'token': key,
            'username': credentials.username,
            'password': credentials.password}
        )
        return {"token": key}

    except exceptions.LoginError:
        res = "Login Error"
        response.status_code = HTTP_400_BAD_REQUEST
        return {response.status_code: res}

    response.status_code = HTTP_500_INTERNAL_SERVER_ERROR
    return {response.status_code: "Server error."}