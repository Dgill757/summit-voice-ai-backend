from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def list_users():
    return {'items': [], 'message': 'User management scaffold ready'}
