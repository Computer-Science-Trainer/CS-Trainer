from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from services.admin_service import (
    get_current_questions, get_proposed_questions,
    add_question, update_question, delete_question,
    approve_proposed_question, reject_proposed_question,
    get_settings, add_proposed_question, update_proposed_question,
    is_user_admin
)


def admin_required(
    authorization: str = Header(None, alias="Authorization")
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "missing_token"}
        )
    token = authorization.split(" ", 1)[1]
    from security import decode_access_token
    from jwt import ExpiredSignatureError, InvalidTokenError
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired"}
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token"}
        )
    user_id = payload.get("user_id")
    if not user_id or not is_user_admin(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "not_admin"}
        )


router = APIRouter(dependencies=[Depends(admin_required)])


class QuestionIn(BaseModel):
    question_text: str
    question_type: str
    difficulty: str
    options: List[str]
    correct_answer: List[str]
    topic_code: str
    proposer_id: int


class QuestionOut(BaseModel):
    id: int
    question_text: str
    question_type: str
    difficulty: str
    options: List[str]
    correct_answer: List[str]
    topic_code: str
    proposer_id: Optional[int] = None


class SettingsOut(BaseModel):
    frontend_url: str
    smtp_host: str
    smtp_port: int
    from_email: str
    google_client_id: str
    github_client_id: str


@router.get('/questions', response_model=List[QuestionOut])
def list_questions():
    return get_current_questions()


@router.post('/questions', response_model=QuestionOut, status_code=201)
def create_question(q: QuestionIn):
    return add_question(q)


@router.put('/questions/{question_id}', response_model=QuestionOut)
def edit_question(question_id: int, q: QuestionIn):
    updated = update_question(question_id, q)
    if not updated:
        raise HTTPException(
            status_code=404, detail={
                'code': 'question_not_found'})
    return updated


@router.delete('/questions/{question_id}', status_code=204)
def remove_question(question_id: int):
    success = delete_question(question_id)
    if not success:
        raise HTTPException(
            status_code=404, detail={
                'code': 'question_not_found'})


@router.get('/proposed', response_model=List[QuestionOut])
def list_proposed():
    return get_proposed_questions()


@router.post('/proposed', response_model=QuestionOut, status_code=201)
def create_proposed(q: QuestionIn):
    return add_proposed_question(q)


@router.put('/proposed/{question_id}', response_model=QuestionOut)
def edit_proposed(question_id: int, q: QuestionIn):
    updated = update_proposed_question(question_id, q)
    if not updated:
        raise HTTPException(
            status_code=404, detail={
                'code': 'proposal_not_found'})
    return updated


@router.post('/proposed/{question_id}/approve', response_model=QuestionOut)
def approve(question_id: int):
    approved = approve_proposed_question(question_id)
    if not approved:
        raise HTTPException(
            status_code=404, detail={
                'code': 'proposal_not_found'})
    return approved


@router.post('/proposed/{question_id}/reject', status_code=204)
def reject(question_id: int):
    success = reject_proposed_question(question_id)
    if not success:
        raise HTTPException(
            status_code=404, detail={
                'code': 'proposal_not_found'})


@router.get('/settings', response_model=SettingsOut)
def settings():
    return get_settings()
