# mtoss_bot

MT5·토스증권 시스템 트레이딩 플랫폼의 브로커 독립 주문 실행 코어와 운영 콘솔 웹앱입니다.

현재 단계는 의도적으로 `FakeBroker`로 제한되어 있습니다. MT5나 토스증권 브로커 어댑터,
실제 브로커 엔드포인트, 실주문 호출은 아직 없습니다.

## 저장소 구성

| 경로 | 내용 |
|---|---|
| `src/mtoss/` | 주문 실행 코어 (Python 3.12 · FastAPI · SQLAlchemy) |
| `src/mtoss/api/console/` | 운영 콘솔용 스텁 API와 한국어 목업 데이터 |
| `web/` | 운영 콘솔 웹앱 (Next.js · TypeScript) |
| `docs/superpowers/` | 시스템 설계서, 화면 설계서, 구현 계획 |
| `alembic/` | 데이터베이스 마이그레이션 |
| `tests/` | 단위·API·통합 테스트 |

## 요구 사항

- Python 3.12와 `uv`
- 웹 콘솔을 실행하려면 Node.js 20 이상
- 로컬 PostgreSQL 16과 Redis를 위한 Docker (`--wait`를 지원하는 Docker Compose 버전)

**Docker가 필요한 작업**: 마이그레이션과 통합 테스트.

**Docker 없이 되는 작업**: 콘솔 스텁 API, 웹 콘솔, 단위·API 테스트. 콘솔 화면만 확인하려면
PostgreSQL과 Redis를 띄우지 않아도 됩니다.

## 로컬 시작

1. `.env.example`을 `.env`로 복사하고 `INTERNAL_API_KEY`를 로컬 비밀값으로 바꿉니다.
2. 의존 서비스를 시작하고 헬스체크를 기다립니다:
   `docker compose up -d --wait db redis`.
3. 잠긴 의존성을 설치합니다: `uv sync --all-groups --locked`.
4. 데이터베이스 마이그레이션을 적용합니다: `uv run --env-file .env alembic upgrade head`.
5. API를 시작합니다:
   `uv run --env-file .env uvicorn mtoss.api.app:create_app --factory --reload`.

Docker를 다른 위치에 노출하지 않았다면 `.env.example`의 로컬 URL을 그대로 사용하세요.
`.env` 파일은 Git이 무시하며 실제 브로커 자격증명을 담아서는 안 됩니다.

## 웹 콘솔 실행

콘솔은 스텁 API(포트 8100)와 Next.js 개발 서버(포트 3100) 두 프로세스로 동작합니다.
PostgreSQL·Redis·Docker는 필요하지 않습니다.

준비는 한 번만 하면 됩니다.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# .env 에서 CONSOLE_STUB_ENABLED=true 로 바꾸고 INTERNAL_API_KEY 를 정합니다.
uv sync --all-groups --locked
npm --prefix web install
Copy-Item web/.env.local.example web/.env.local
```

`web/.env.local`의 `INTERNAL_API_KEY`는 저장소 루트 `.env`의 값과 같아야 합니다.
다르면 모든 화면이 401로 비어 보입니다.

터미널 1 — 스텁 API:

```powershell
uv run --env-file .env uvicorn mtoss.api.app:create_app --factory --reload --host 127.0.0.1 --port 8100
```

터미널 2 — 웹 콘솔:

```powershell
npm --prefix web run dev
```

브라우저에서 <http://127.0.0.1:3100/dashboard>를 엽니다.

스텁 상태는 프로세스 메모리에만 있습니다. `--reload`로 파이썬 파일이 다시 로드되면 초기화되며,
`POST /console/v1/controls/reset`으로도 초기화할 수 있습니다. 워커를 여러 개(`--workers`)
띄우면 워커마다 상태가 달라지므로 단일 워커로만 실행하세요.

## 콘솔 화면

| 화면 | 경로 |
|---|---|
| 대시보드 | `/dashboard` |
| 전략 목록·상세 | `/strategies`, `/strategies/{id}` |
| 카피트레이딩 | `/copy` |
| 승인함 | `/approvals` |
| 주문·포지션 | `/orders` |
| 위험 설정 | `/risk` |
| 연결 | `/connections` |
| 감사 기록 | `/audit` |
| 관리자 | `/admin` |
| 로그인·MFA | `/login` |
| 첫 설정 온보딩 | `/onboarding` |

화면 기준은 `docs/superpowers/specs/2026-08-18-claude-design-ui-spec.md`입니다. 라이트·다크
테마는 좌측 하단에서 전환하며 선택은 쿠키에 저장됩니다. 선택하지 않으면 운영체제 설정을
따릅니다.

`?role=TRADER` 또는 `?role=VIEWER`를 붙이면 역할별 화면을 확인할 수 있습니다. 권한이 없는
기능은 비활성화되지 않고 아예 숨겨집니다.

## 콘솔 스텁 API

> **경고:** `/console/v1`은 한국어 목업 데이터만 내려주며 실제 계좌·주문과 무관합니다.
> `CONSOLE_STUB_ENABLED`는 기본값이 `false`이며, 운영 환경에서 켜서는 안 됩니다.

실행 코어와 같은 `X-Internal-Key` 헤더로 보호됩니다. Next.js가 서버 사이드에서만 헤더를
붙이므로 키가 브라우저로 나가지 않습니다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/console/v1/session` | 사용자·역할·계좌 범위·시스템 상태 |
| GET | `/console/v1/dashboard` | 대시보드 전체 |
| GET | `/console/v1/strategies`, `/strategies/{id}` | 전략 목록·상세 |
| GET | `/console/v1/copy-sources`, `/copy-sources/{id}` | 리더·외부 신호·13F |
| GET | `/console/v1/approvals`, `/approvals/{id}` | 승인 목록(만료 임박 순)·상세 |
| POST | `/console/v1/approvals/{id}/recheck` | 가격·계좌 상태 재검사 |
| POST | `/console/v1/approvals/{id}/decide` | 실제 `ApprovalPolicy.decide()` 호출 |
| GET | `/console/v1/orders`, `/orders/{id}` | 주문·체결·포지션·정합성 |
| POST | `/console/v1/orders/{id}/recheck-broker` | 브로커 상태 다시 확인 |
| GET/PATCH | `/console/v1/risk-rules` | 위험 한도 조회·변경 |
| GET | `/console/v1/connections` | 토스 계좌와 MT5 노드 |
| POST | `/console/v1/connections/toss/test` | 연결 테스트 (실패 원인 구분) |
| GET | `/console/v1/audit`, `/audit/{id}` | 감사 기록과 관계 추적 |
| GET | `/console/v1/admin` | 관리자 화면 |
| GET/POST | `/console/v1/controls/...` | 긴급 정지·전량 청산·초기화 |

`UNKNOWN` 주문을 재전송하는 엔드포인트는 **의도적으로 존재하지 않습니다.** 제공되는 동작은
브로커 상태 재확인뿐입니다.

동작 확인:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8100/console/v1/dashboard" `
  -Headers @{ "X-Internal-Key" = "<.env 의 INTERNAL_API_KEY>" } | ConvertTo-Json -Depth 6
```

## 상태 시뮬레이터

화면 설계서 §9의 모든 상태를 `?state=` 쿼리로 재현할 수 있습니다. `NEXT_PUBLIC_STATE_SIM=1`이면
상단 바에 선택기가 나타납니다.

| 슬러그 | 화면 |
|---|---|
| `normal` | 정상 데이터 |
| `loading` | 최초 로딩 skeleton |
| `empty` | 데이터 없음 |
| `partial` | 일부 데이터만 성공 |
| `forbidden` | 권한 없음 (403) |
| `server-error` | 서버 오류와 재시도 (503) |
| `market-data-stale` | 시장 데이터 지연 |
| `rate-limited` | 브로커 호출 제한 |
| `toss-auth-expired` | 토스 인증 만료 |
| `mt5-offline` | MT5 노드 offline |
| `strategy-error` | 전략 오류로 해당 전략만 정지 |
| `emergency-stop` | 전체 긴급 정지 |
| `position-mismatch` | 수동 거래로 인한 포지션 불일치 |

예: <http://127.0.0.1:3100/connections?tab=mt5&state=mt5-offline>

## 검사

PostgreSQL과 Redis가 실행 중이고 마이그레이션이 적용된 상태에서 전체 스위트를 실행합니다.

```shell
uv run --env-file .env pytest tests -v
```

CI가 사용하는 개별 검사는 다음과 같습니다.

```shell
uv run --env-file .env pytest tests/integration -v
uv run --env-file .env pytest tests/unit tests/api -v
uv run ruff check .
uv run mypy src/mtoss
```

웹 콘솔 검사:

```shell
npm --prefix web run typecheck
npm --prefix web run build
```

## 화면 검증

Playwright가 스텁 API와 웹 서버를 직접 띄우므로 명령 하나로 끝납니다. 브라우저는 한 번만
설치하면 됩니다.

```shell
npm --prefix web exec playwright install chromium
npm --prefix web run e2e      # 제품 규칙과 접근성 검증
npm --prefix web run shots    # 스크린샷 저장
```

`npm run e2e`는 다음을 화면에서 직접 확인합니다.

- 승인함 목록에서 바로 승인할 수 없고 `상세 검토`만 제공한다
- 승인 전 가격 재검사에서 조건이 바뀌면 다시 확인받는다
- `UNKNOWN` 주문에 재주문 버튼이 없고 `브로커 상태 다시 확인`만 있다
- 전체 긴급 정지는 재인증을 요구하고 포지션을 청산하지 않는다
- 긴급 정지 배너가 모든 화면에 뜨고 닫히지 않는다
- 전량 청산은 확인 문구와 재인증이 모두 있어야 실행된다
- MT5 노드가 재연결돼도 자동으로 매매를 재개하지 않는다
- 조회 전용 역할에서 위험 설정·연결·관리자 메뉴가 숨겨진다
- 라이트·다크 모두 WCAG 2.2 AA 위반이 없다 (axe-core)

`npm run shots`는 데스크톱 1440px, 태블릿 1024px, 모바일 390px에서 라이트·다크 화면을
`web/screenshots/`에 저장합니다. 이 디렉터리는 Git이 무시합니다.

## 마이그레이션 검증

아래의 일회용 데이터베이스를 사용합니다. 개발용 `mtoss` 데이터베이스와 분리되어 있으며,
이 명령들이 삭제하는 유일한 데이터베이스입니다.

Bash:

```bash
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
docker compose exec -T db createdb -U mtoss mtoss_ci_verify
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run --env-file .env alembic upgrade head
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run --env-file .env alembic downgrade base
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run --env-file .env alembic upgrade head
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
```

PowerShell:

```powershell
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
docker compose exec -T db createdb -U mtoss mtoss_ci_verify
$env:DATABASE_URL = "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify"
uv run --env-file .env alembic upgrade head
uv run --env-file .env alembic downgrade base
uv run --env-file .env alembic upgrade head
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
Remove-Item Env:DATABASE_URL
```

일회용 데이터베이스 mtoss_ci_verify에는 보존할 데이터가 없습니다. 이 마이그레이션 검사만을
위해 존재하며 왕복 검증이 끝나면 의도적으로 삭제됩니다.

## 백업과 복구

데이터베이스 볼륨을 제거할 수 있는 작업을 하기 전에 호스트 쪽 백업을 만드세요. `backups/`
디렉터리는 Git이 무시하므로, 로컬 데이터가 중요하다면 그 내용을 별도로 보호하고 보관해야
합니다. Bash에서는 `mkdir -p backups`로, PowerShell에서는
`New-Item -ItemType Directory -Force backups | Out-Null`로 먼저 만듭니다.

```shell
docker compose exec -T db pg_dump -U mtoss -d mtoss --format=custom --file=/tmp/mtoss.dump
docker compose cp db:/tmp/mtoss.dump ./backups/mtoss.dump
docker compose exec -T db rm -f /tmp/mtoss.dump
```

새 로컬 데이터베이스나 기존 데이터베이스를 복구하려면 API와 이를 사용하는 모든 프로세스를
멈춘 뒤 의존 서비스를 정상 상태로 시작합니다. 아래 명령들은 백업을 복원하기 전에 로컬 mtoss
데이터베이스의 기존 데이터를 영구적으로 삭제합니다. `dropdb --force`는 해당 데이터베이스
하나의 활성 연결만 종료하며, `postgres_data` 볼륨이나 PostgreSQL 서비스의 다른 데이터베이스는
제거하지 않습니다. 각 명령을 따로 실행하고 종료 코드가 0이 아니면 멈추세요. `dropdb`와
`createdb`가 모두 성공하지 않았다면 복원하지 마세요.

```shell
docker compose up -d --wait db redis
docker compose cp ./backups/mtoss.dump db:/tmp/mtoss.dump
docker compose exec -T db dropdb -U mtoss --if-exists --force mtoss
docker compose exec -T db createdb -U mtoss -O mtoss mtoss
docker compose exec -T db pg_restore -U mtoss -d mtoss --exit-on-error /tmp/mtoss.dump
docker compose exec -T db rm -f /tmp/mtoss.dump
uv run --env-file .env alembic upgrade head
```

컨테이너 안의 복사본은 `pg_restore`가 성공한 뒤에만 지우세요. 복원에 실패하면 호스트 쪽
`backups/mtoss.dump`를 그대로 두고 drop/create/restore 절차를 다시 수행하며, 복원과 마지막
마이그레이션이 모두 성공하기 전에는 API를 다시 시작하지 마세요.

## 중지와 볼륨 안전

일반적인 `docker compose down`은 컨테이너를 멈추고 제거하지만 이름이 지정된 `postgres_data`
볼륨은 보존하므로 다음 시작 때 로컬 데이터베이스를 그대로 사용할 수 있습니다.
`docker compose down -v`는 로컬 데이터베이스 볼륨을 영구적으로 삭제하며, 호스트 쪽 백업이
없으면 그 데이터는 복원할 수 없습니다. `-v`는 의도적으로 초기화할 때, 또는 위의 백업·복구
절차를 검증한 뒤에만 사용하세요.

## 안전

이 단계에는 `FakeBroker`만 있으므로 실주문을 낼 수 없습니다. 실제 브로커 자격증명을 설정하거나
저장하거나 커밋하지 마세요.

`UNKNOWN` 상태의 주문은 브로커 결과가 확정되지 않은 것이며 수동으로 정합성을 맞춰야 합니다.
자동으로 재시도하거나 재전송해서는 안 됩니다.

콘솔 화면의 긴급 정지, 계좌 정지, 전량 청산은 현재 목업 동작입니다. 실제 브로커에 아무 영향도
주지 않으며, 실 브로커 어댑터가 붙은 뒤 다시 검증해야 합니다.
