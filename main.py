import ssl
from uuid import uuid4
from tinydb import TinyDB, Query
from tinydb.queries import where
from fastapi import FastAPI, Header
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

@app.get("/select/")
async def select(mailbox: str, token: str = Header(None)):
    m = connect_imap(token)
    box = m.select_folder(mailbox)
    messages = m.search()
    lista = []
    for mid, data in m.fetch(messages, ['ENVELOPE']).items():
        envelope = data[b'ENVELOPE']
        lista.append(
            {
                "id": mid,
                "subject": envelope.subject.decode(),
                "date": envelope.date,
                "sender": envelope.sender,
                "to": envelope.to,
                "bcc": envelope.bcc,
                "cc": envelope.cc,
                # "count": envelope.count,
                "in_reply_to": envelope.in_reply_to,
                "reply_to": envelope.reply_to,
            })
    return lista

@app.get("/mailboxes/")
async def mailboxes(response: Response, token: str = Header(None)):
    m = connect_imap(token)

    if not m:
        response.status_code = HTTP_401_UNAUTHORIZED
        return None

    folders = m.list_folders()
    return folders

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