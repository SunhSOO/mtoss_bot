# mtoss_bot

MT5·토스증권 시스템 트레이딩 플랫폼의 브로커 독립 주문 실행 코어와 운영 콘솔 웹앱입니다.

**실주문은 아직 나가지 않습니다.** MT5 읽기(진단·심볼 스펙·봉)와 주문 계약·배관은 준비됐지만
MT5 어댑터 본체가 미구현입니다. 남은 작업은 [이슈 목록](https://github.com/SunhSOO/mtoss_bot/issues)에
정리돼 있습니다.

## 현재 상태

| 구성 요소 | 상태 |
|---|---|
| 주문 실행 코어 (리스크·승인·상태기계) | ✅ |
| UT Bot 전략 (신호·2트랜치 상태기계·사이징·백테스트) | ✅ |
| 아웃박스 실행 워커 | ✅ FakeBroker까지 |
| MT5 읽기 (진단·심볼 스펙·봉·리트코드 매핑·선행기록) | ✅ |
| 텔레그램 알림·확인 버튼 | ✅ 토큰 설정 시 |
| MT5 실주문 | ❌ [#4](https://github.com/SunhSOO/mtoss_bot/issues/4) |
| H1 자동 스케줄러 | ❌ [#7](https://github.com/SunhSOO/mtoss_bot/issues/7) |
| 콘솔 실데이터 | ❌ [#14](https://github.com/SunhSOO/mtoss_bot/issues/14) — 지금은 목업 |

## 저장소 구성

| 경로 | 내용 |
|---|---|
| `src/mtoss/domain/` | 주문·봉·리스크·확인 요청 도메인 모델 |
| `src/mtoss/application/` | 인텐트 생성, 리스크, 승인, 트레이드 매니저, 사이징 |
| `src/mtoss/strategies/ut_bot/` | UT Bot 지표·신호·백테스트 |
| `src/mtoss/infrastructure/` | DB, 브로커 어댑터(Fake·MT5), 텔레그램 |
| `src/mtoss/workers/` | 아웃박스 실행 워커 |
| `src/mtoss/api/console/` | 운영 콘솔용 스텁 API와 한국어 목업 데이터 |
| `web/` | 운영 콘솔 웹앱 (Next.js · TypeScript) |
| `ops/` | 운영 스크립트 (MT5 진단 등) |
| `docs/deployment/` | [미니PC 배포 절차서](docs/deployment/mini-pc.md) |
| `docs/superpowers/` | 시스템 설계서, 화면 설계서, 구현 계획 |
| `alembic/` | 데이터베이스 마이그레이션 |
| `tests/` | 단위·API·통합 테스트 |

## 요구 사항

- Python 3.12와 `uv`
- PostgreSQL 16 이상 (17로 검증). **Windows에서는 네이티브 설치를 권장합니다** — Docker Desktop은
  WSL2/Hyper-V를 요구하고 자동 업데이트가 데이터베이스를 재시작시킵니다.
- 웹 콘솔을 실행하려면 Node.js 20 이상
- MT5 기능을 쓰려면 Windows + INFINOX MetaTrader 5 터미널

**Redis는 선택 사항입니다.** 실행 경로는 PostgreSQL 아웃박스만 쓰므로 Redis 없이도 주문이 나갑니다.
`.env`에 `REDIS_URL`이 있으면 헬스체크가 접속을 시도하니, 설치하지 않았다면 그 줄을 지우세요.

**PostgreSQL 없이 되는 작업**: 콘솔 스텁 API, 웹 콘솔, 단위·API 테스트, 전략 백테스트.

`compose.yaml`은 개발 편의용입니다. 미니PC 배포에는 쓰지 않습니다 —
[배포 절차서](docs/deployment/mini-pc.md)를 보세요.

## 로컬 시작

1. `.env.example`을 `.env`로 복사하고 `INTERNAL_API_KEY`를 로컬 비밀값으로 바꿉니다.
2. PostgreSQL을 준비합니다. 네이티브 설치라면 역할과 데이터베이스를 만듭니다:
   ```powershell
   $psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
   & $psql -U postgres -h localhost -c "CREATE ROLE mtoss LOGIN PASSWORD 'mtoss'"
   & $psql -U postgres -h localhost -c "CREATE DATABASE mtoss OWNER mtoss"
   ```
   Docker를 쓴다면 `docker compose up -d --wait db` 로도 됩니다.
3. 의존성을 설치합니다: `uv sync --all-groups`
   (MT5 기능까지 쓰려면 Windows에서 `uv sync --all-groups --extra mt5`)
4. 마이그레이션을 적용합니다: `uv run --env-file .env alembic upgrade head`
5. API를 시작합니다:
   `uv run --env-file .env uvicorn mtoss.api.app:create_app --factory --reload`

`.env` 파일은 Git이 무시하며 실제 브로커 자격증명이나 텔레그램 토큰을 커밋해서는 안 됩니다.

## 전략 — UT Bot 2-포지션 분할

TradingView Pine v6 전략을 파이썬으로 옮긴 것입니다. **XAUUSD+, H1** 기준.

신호가 나면 주문 **2개**를 같은 방향으로 넣습니다.

| | 손절 | 익절 | 성격 |
|---|---|---|---|
| **T1** | 최근 4봉 최저(롱)/최고(숏) | 손절폭 × `rr_mult` | 고정 1:1 |
| **T2** | 같은 자리 | 없음 | 러너 |

T1이 익절되면 T2의 손절을 **본절(진입가)** 로 올립니다. Hull 밴드 색이 뒤집히면 T2만 청산하고,
반대 신호가 오면 전부 청산 후 반대 방향으로 재진입합니다.

**헤징 계좌가 필수입니다.** 넷팅은 심볼당 순포지션 1개·SL/TP 1쌍뿐이라 서로 다른 손절을 동시에
들 수 없습니다. 헤징이면 SL/TP가 브로커 서버에 걸려 **이 서버가 꺼져 있어도 손절이 작동합니다.**

### 수량 산정

```
lots = (자본 × 리스크%) ÷ (R × 계약크기)      # R = |진입가 − 손절가|
```

`base_lots`(하한)와 `max_lots`(상한) 사이로 자르고 브로커 `volume_step`으로 **내림**합니다.
최소 단위로도 예산을 넘으면 자동 진입하지 않고 **텔레그램으로 확인을 요청합니다.**
무응답은 건너뛰기입니다.

Pine과 의도적으로 다른 두 지점은 [trade_manager.py](src/mtoss/application/trade_manager.py) 상단에
적혀 있습니다.

## MT5 진단

주문을 내지 않고 계좌·심볼 스펙만 읽습니다. 배포 전과 브로커 설정이 바뀔 때마다 돌리세요.

```powershell
uv run --extra mt5 python ops/mt5_probe.py
```

`margin_mode`, 금 심볼별 계약 크기·거래모드·`stops_level`·필링 모드, R별 랏 표,
`order_check` 증거금, 서버 시각 오프셋을 출력합니다.

> 서버 시각 오프셋은 **장중에만** 계산됩니다. 휴장 중에는 마지막 틱 시각이라 의미가 없습니다.

## 텔레그램 알림

`.env`에 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`를 넣으면 켜집니다. 만드는 방법은
[배포 절차서 §7](docs/deployment/mini-pc.md#7-텔레그램)에 있습니다.

**롱폴링(`getUpdates`)을 씁니다.** 웹훅과 달리 아웃바운드 HTTPS만 쓰므로 개방 포트가 필요 없습니다.

`TELEGRAM_CHAT_ID`는 보안 장치입니다. 이 id에서 온 콜백만 받아들입니다 — 없으면 봇 이름을
알아낸 누구나 실계좌 진입 버튼을 누를 수 있습니다.

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

PostgreSQL이 실행 중이고 마이그레이션이 적용된 상태에서 전체 스위트를 실행합니다.

```shell
uv run --env-file .env pytest tests -v
```

`tests/integration/test_redis_publisher.py`는 Redis를 요구합니다. Redis를 설치하지 않았다면
그 파일만 빼면 나머지 통합 테스트는 전부 돕니다.

```shell
uv run --env-file .env pytest tests/integration -q --ignore=tests/integration/test_redis_publisher.py
```

PostgreSQL 없이 돌릴 수 있는 검사 (CI가 쓰는 것):

```shell
uv run --env-file .env pytest tests/unit tests/api -v
uv run ruff check .
uv run mypy src/mtoss
```

웹 콘솔 검사:

```shell
npm --prefix web run build
npm --prefix web run typecheck
```

`next-env.d.ts`는 Next가 자동 생성하며 `dev`와 `build`가 서로 다른 경로를 쓰므로 Git이
무시합니다. 새로 클론했다면 `typecheck` 전에 `build`나 `dev`를 한 번 실행해야 합니다.

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

**네이티브 PostgreSQL** (미니PC 구성):

```powershell
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$env:PGPASSWORD = "<superpassword>"
& $psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS mtoss_ci_verify"
& $psql -U postgres -h localhost -c "CREATE DATABASE mtoss_ci_verify OWNER mtoss"
$env:PGPASSWORD = $null

$env:DATABASE_URL = "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify"
uv run --env-file .env alembic upgrade head
uv run --env-file .env alembic downgrade base
uv run --env-file .env alembic upgrade head
$env:DATABASE_URL = $null

$env:PGPASSWORD = "<superpassword>"
& $psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS mtoss_ci_verify"
$env:PGPASSWORD = $null
```

아래는 Docker를 쓰는 개발 환경용입니다.

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

> 아래는 **Docker를 쓰는 개발 환경** 절차입니다. 네이티브 PostgreSQL(미니PC)은
> [배포 절차서 §10](docs/deployment/mini-pc.md#10-백업)을 보세요.
>
> 어느 쪽이든 원칙은 같습니다 — **복구를 실제로 테스트하기 전에는 백업이 아닙니다.**

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

> Docker를 쓰는 개발 환경에만 해당합니다. 미니PC는 네이티브 PostgreSQL 서비스를 씁니다.

일반적인 `docker compose down`은 컨테이너를 멈추고 제거하지만 이름이 지정된 `postgres_data`
볼륨은 보존하므로 다음 시작 때 로컬 데이터베이스를 그대로 사용할 수 있습니다.
`docker compose down -v`는 로컬 데이터베이스 볼륨을 영구적으로 삭제하며, 호스트 쪽 백업이
없으면 그 데이터는 복원할 수 없습니다. `-v`는 의도적으로 초기화할 때, 또는 위의 백업·복구
절차를 검증한 뒤에만 사용하세요.

## 안전

현재 MT5 어댑터 본체가 없어 실주문이 나가지 않습니다. 붙인 뒤에도 `MT5_SUBMIT_ENABLED`가
기본값 `false`라 `order_send`만 차단된 섀도 모드로 돕니다 — 실계좌 전 마지막 안전장치입니다.

실계좌에 켜기 전 반드시 있어야 하는 것은
[배포 절차서 §12](docs/deployment/mini-pc.md#12-실계좌-전-필수-항목)에 정리돼 있습니다.

브로커 비밀번호와 텔레그램 토큰은 가능하면 Windows 자격증명 관리자에 두고 `.env`에 남기지 마세요.
어느 쪽이든 커밋해서는 안 됩니다.

### 이 계좌에서 알고 있어야 할 숫자

자본 $389.57, `XAUUSD+`는 100oz 계약이라 **0.01랏 = 1oz**입니다. 손절 시 손실이 곧 R달러입니다.
최소 거래 단위가 이미 리스크 예산 근처라 **사이징이 수량을 줄일 여지가 거의 없습니다.**
트레이드당 자본의 10~20%가 걸립니다.

레버리지가 1:1000이라 증거금은 제약이 아닙니다(0.04랏에 $18). **브로커가 막아 주지 않는다는
뜻**이고, `max_lots` 상한이 유일한 브레이크입니다.

`UNKNOWN` 상태의 주문은 브로커 결과가 확정되지 않은 것이며 수동으로 정합성을 맞춰야 합니다.
자동으로 재시도하거나 재전송해서는 안 됩니다.

콘솔 화면의 긴급 정지, 계좌 정지, 전량 청산은 현재 목업 동작입니다. 실제 브로커에 아무 영향도
주지 않으며, 실 브로커 어댑터가 붙은 뒤 다시 검증해야 합니다.
