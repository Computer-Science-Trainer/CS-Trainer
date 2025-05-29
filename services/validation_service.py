from fastapi import HTTPException
from starlette import status
from typing import List


def validate_question_text(text: str) -> None:
    if not isinstance(text, str) or not text.strip() or len(text) > 512:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_question_text"}
        )


def validate_option_list(
        qtype: str, items: List[str], code_prefix: str = "option") -> None:
    if qtype == 'open-ended':
        if len(items) != 1 or not isinstance(
                items[0], str) or len(items[0]) > 128:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": f"invalid_{code_prefix}"}
            )
    else:
        if len(items) > 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": f"too_many_{code_prefix}s"}
            )
        for item in items:
            if not isinstance(item, str) or len(item) > 128:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": f"invalid_{code_prefix}_length"}
                )
