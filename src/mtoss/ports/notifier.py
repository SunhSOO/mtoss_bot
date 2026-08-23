from typing import Protocol

from mtoss.domain.confirmations import ConfirmationRequest, ConfirmationResponse


class Notifier(Protocol):
    """사람에게 알리고 답을 받아 오는 통로."""

    async def notify(self, text: str) -> None:
        """버튼 없는 정보성 알림. 실패해도 매매를 막지 않는다."""
        ...

    async def request_confirmation(self, request: ConfirmationRequest) -> None:
        """버튼 달린 확인 요청. 답이 오기 전에는 진입하지 않는다."""
        ...

    async def poll_responses(self, timeout_seconds: int = 25) -> tuple[ConfirmationResponse, ...]:
        """도착한 응답을 가져온다. 같은 응답이 두 번 올 수 있으므로 처리는 멱등해야 한다."""
        ...
