from fastapi import APIRouter

router = APIRouter()


@router.get('/')
async def list_subscriptions():
    return {'items': [], 'message': 'Subscription management scaffold ready'}
