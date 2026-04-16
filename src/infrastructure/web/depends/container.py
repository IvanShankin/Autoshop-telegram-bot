from fastapi import Request

from src.containers.app_container import AppContainer


def get_container(request: Request):
    app_container: AppContainer = request.app.state.container
    return app_container.get_request_container_factory()
