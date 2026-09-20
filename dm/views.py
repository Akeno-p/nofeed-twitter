from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.utils import request_with_token_refresh
from common.x_api_client import (
    DirectMessageResponseData,
    MediaResponseData,
    get_dm_events,
    get_users,
    post_dm_request,
)
from dm.models import Conversation, DirectMessage, DirectMessageMedia
from users.models import XUser

# X API で取得できるDMの期間(日)
DM_EVENTS_AVAILABLE_DAYS = 30

# 新着確認のために最初に取得するDMの件数
FIRST_REQUEST_MAX_RESULTS = 10

# 新着が多い場合に、取得し直す時の1回あたりのDMの件数
FULL_FETCH_MAX_RESULTS = 100

# ユーザー情報を1回のリクエストで取得できる件数
GET_USERS_MAX_IDS = 100


@login_required
def dm_view(request):
    """DMページを開いた時の処理"""
    conversations = Conversation.objects.for_display(request.user)

    return render(request, "dm/dm.html", {"conversations": conversations})


@require_POST
@login_required
def save_all_dms(request):
    """DM取得ボタンを押した時の処理"""
    status, message = "success", None

    last_dm = DirectMessage.objects.last_dm()
    available_since = timezone.now() - timedelta(days=DM_EVENTS_AVAILABLE_DAYS)

    if last_dm and last_dm.created_at < available_since:
        last_dm_created_at = timezone.localtime(last_dm.created_at)
        last_dm_created_at_display = last_dm_created_at.strftime("%Y年%m月%d日")

        status, message = (
            "partial",
            (
                "Xの仕様により、取得できるのは直近30日分のDMのみです。"
                f"保存されている最新のDMは{last_dm_created_at_display}のものなので、"
                "それ以降に届いたDMの一部が取得できていない可能性があります。"
            ),
        )

    saved_dm_ids = set(DirectMessage.objects.all_dm_ids())

    fetch_status, fetch_result = _fetch_new_dms(request, saved_dm_ids)

    if fetch_status == "error":
        return JsonResponse(fetch_result)

    dm_responses, media_responses = fetch_result

    # グループDMは対象に含めない
    one_to_one_dm_responses = [
        response
        for response in dm_responses
        if Conversation.is_one_to_one(response["dm_conversation_id"])
    ]

    save_status, save_result = _save_dms(
        request, one_to_one_dm_responses, media_responses
    )

    if save_status == "error":
        return JsonResponse(save_result)

    conversations = Conversation.objects.for_display(request.user)

    html = render_to_string(
        "dm/_dm_body.html", {"conversations": conversations}, request=request
    )

    return JsonResponse({"status": status, "message": message, "html": html})


@require_POST
@login_required
def post_dm(request):
    """DMの送信ボタンを押した時の処理"""
    dm_text = request.POST.get("dmText")
    conversation_id = request.POST.get("conversationId")

    conversation = Conversation.objects.filter(id=conversation_id).first()

    if conversation is None:
        return JsonResponse(
            {"status": "exception", "message": "送信先の会話が見つかりませんでした。"}
        )

    status, result = request_with_token_refresh(
        request, post_dm_request, conversation.dm_conversation_id, dm_text
    )

    if status == "error":
        return JsonResponse(result)

    dm_event_id = result.json()["data"]["dm_event_id"]

    # 送信のレスポンスには本文や送信日時が入っていないため、手元の値で保存している。
    # 取り直す場合、DMには1件だけ取得するエンドポイントがなく、別途料金がかかる。
    direct_message = DirectMessage.objects.create_sent_dm(
        dm_event_id, conversation, request.user, dm_text
    )

    Conversation.objects.update_last_message_at(conversation, direct_message.created_at)

    conversations = Conversation.objects.for_display(request.user)

    html = render_to_string(
        "dm/_dm_body.html", {"conversations": conversations}, request=request
    )

    return JsonResponse({"status": "success", "html": html})


def _fetch_new_dms(request, saved_dm_ids: set[int]):
    """新着のDMを新しい順に取得する。

    DMは新しい順に返ってくるため、保存済みのDMが含まれるページまで取得したら打ち切る。
    料金を抑えるため、まず FIRST_REQUEST_MAX_RESULTS 件だけ取得し、その中に保存済みのDMが
    なければ、最初から FULL_FETCH_MAX_RESULTS 件ずつ取得し直す。
    (同じ日付(UTC)内に同じDMを取得しても再度課金はされないため、取得し直した分の料金はかからない)

    戻り値は、
    第一引数にstatus : error or success
    第二引数にerrorの場合はerror詳細 successの場合は(DMのリスト, メディアのリスト)
    """
    status, result = _fetch_dm_page(request, FIRST_REQUEST_MAX_RESULTS)

    if status == "error":
        return status, result

    dm_responses, media_responses, next_token = result

    if not next_token or _contains_saved_dm(dm_responses, saved_dm_ids):
        return "success", (dm_responses, media_responses)

    # 新着が多かったため、最初から取得し直す
    dm_responses = []
    media_responses = []
    next_token = None

    while True:
        status, result = _fetch_dm_page(request, FULL_FETCH_MAX_RESULTS, next_token)

        if status == "error":
            return status, result

        page_dm_responses, page_media_responses, next_token = result
        dm_responses.extend(page_dm_responses)
        media_responses.extend(page_media_responses)

        if not next_token or _contains_saved_dm(page_dm_responses, saved_dm_ids):
            return "success", (dm_responses, media_responses)


def _fetch_dm_page(request, max_results: int, next_token: str | None = None):
    """DMを1ページ分取得する。

    戻り値は、
    第一引数にstatus : error or success
    第二引数にerrorの場合はerror詳細 successの場合は(DMのリスト, メディアのリスト, 次ページのトークン)
    """
    status, result = request_with_token_refresh(
        request, get_dm_events, max_results, next_token
    )

    if status == "error":
        return status, result

    body = result.json()
    dm_responses = body.get("data", [])
    media_responses = body.get("includes", {}).get("media", [])
    next_token = body.get("meta", {}).get("next_token")

    return "success", (dm_responses, media_responses, next_token)


def _contains_saved_dm(
    dm_responses: list[DirectMessageResponseData], saved_dm_ids: set[int]
) -> bool:
    """DMのリストに保存済みのDMが含まれていれば True を返す"""
    return any(int(response["id"]) in saved_dm_ids for response in dm_responses)


def _save_dms(
    request,
    dm_responses: list[DirectMessageResponseData],
    media_responses: list[MediaResponseData],
):
    """保存したい1対1のDMのレスポンスをリストにして渡すと、会話相手・会話・DM・メディアが保存される。

    戻り値は、
    第一引数にstatus : error or success
    第二引数にerrorの場合はerror詳細 successの場合はNone
    """
    participant_ids = Conversation.objects.participant_ids(dm_responses, request.user)
    not_saved_user_ids = XUser.objects.not_saved_user_ids(participant_ids)

    x_user_responses = []

    for start in range(0, len(not_saved_user_ids), GET_USERS_MAX_IDS):
        user_ids = not_saved_user_ids[start : start + GET_USERS_MAX_IDS]

        status, result = request_with_token_refresh(request, get_users, user_ids)

        if status == "error":
            return status, result

        # 凍結・削除されたユーザーは "data" に含まれない
        x_user_responses.extend(result.json().get("data", []))

    XUser.objects.bulk_create_from_responses(x_user_responses)
    saved_user_ids = set(XUser.objects.all_user_ids())

    # 保存の途中で失敗した場合に、DMだけ保存されてメディアが保存されない状態を防ぐため
    with transaction.atomic():
        conversations_by_dm_conversation_id = Conversation.objects.save_from_responses(
            dm_responses, request.user, saved_user_ids
        )

        dm_media_pairs = DirectMessage.objects.bulk_create_from_responses(
            dm_responses, conversations_by_dm_conversation_id, saved_user_ids
        )

        DirectMessageMedia.objects.bulk_create_from_responses(
            media_responses, dm_media_pairs
        )

    return "success", None
