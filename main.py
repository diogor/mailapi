import ssl
from fastapi import FastAPI
from starlette.responses import Response
from starlette.status import HTTP_400_BAD_REQUEST
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

@app.get("/")
async def root():
    m = connect()
    s = m.noop()
    return {"message": s}

@app.post("/login")
async def login(credentials: Login, response: Response):
    m = connect()
    res: str
    try:
        res = m.login(credentials.username, credentials.password)
    except exceptions.LoginError:
        res = "Login Error"
        response.status_code = HTTP_400_BAD_REQUEST
    return {"server": res}