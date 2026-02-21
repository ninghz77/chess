"""FastAPI application factory."""
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

_BASE = os.path.dirname(__file__)
_WEB = os.path.join(_BASE, '..', 'web')


def create_app() -> FastAPI:
    application = FastAPI(
        title='Chess Web App',
        description='Python chess engine with pluggable evaluators and three game modes.',
        version='0.1.0',
    )

    # Routers
    from api.routes.rest import router as rest_router
    from api.routes.ws import router as ws_router

    application.include_router(rest_router)
    application.include_router(ws_router)

    # Static assets
    static_dir = os.path.join(_WEB, 'static')
    application.mount('/static', StaticFiles(directory=static_dir), name='static')

    # Template for the single-page app
    templates = Jinja2Templates(directory=os.path.join(_WEB, 'templates'))

    @application.get('/', response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse('index.html', {'request': request})

    return application


app = create_app()
