# from flask import session
from flask import abort
from http import HTTPStatus
from werkzeug.exceptions import HTTPException, BadRequest
from mylib.auth.TokenProvider import TokenProvider

class FlaskSessionManager:
    @classmethod
    def create_session(cls, flask_session, user_info: dict):
        token = TokenProvider.issue_token(user_info['username'], user_info['role'], user_info['privileges'])
        flask_session['username'] = user_info['username']
        flask_session['role'] = user_info['role']
        flask_session['privileges'] = user_info['privileges']
        # flask_session['token'] = token
        return token

    @classmethod
    def clear_session(cls, flask_session):
        flask_session.clear()

    @classmethod
    def update_session(cls, flask_session, key: str, value):
        flask_session[key] = value

    @classmethod
    def is_authenticated(cls, flask_session) -> bool:
        return 'username' in flask_session and 'privileges' in flask_session

    @classmethod
    def has_privilege(cls, flask_session, required_privilege: str) -> bool:
        return required_privilege in flask_session.get('privileges', [])
    
    @classmethod
    def validate_privilege(cls, flask_session, required_privilege: str) -> bool:
        if not cls.has_privilege(flask_session, required_privilege):
            username = flask_session.get('username')
            abort(HTTPStatus.FORBIDDEN.value, f"Privilege '{required_privilege}' is required for user '{username}'")

