# 미니PC 배포 절차서

항상 켜 두는 Windows 미니PC 한 대에 이 시스템을 올린다. 이 박스가 **중앙 서버와 MT5 노드를 겸한다.**

> **먼저 읽을 것.** 현재 실주문은 나가지 않는다. 아래 "지금 배포 가능한 것"을 확인하고 시작하라.
> 실계좌에 붙이기 전 반드시 통과해야 할 항목은 마지막 절에 있다.

## 지금 배포 가능한 것

| 구성 요소 | 상태 |
|---|---|
| PostgreSQL + 마이그레이션 | ✅ 동작 |
| API 서버 (FastAPI) | ✅ 동작 |
| 아웃박스 실행 워커 | ✅ 동작 (FakeBroker까지) |
| 전략 계산 (UT Bot 신호·사이징·백테스트) | ✅ 동작 |
| MT5 읽기 (진단·심볼 스펙·봉) | ✅ 동작 |
| 텔레그램 알림·확인 버튼 | ✅ 동작 (토큰 설정 시) |
| **MT5 실주문** | ❌ [#4](https://github.com/SunhSOO/mtoss_bot/issues/4) 어댑터 본체 미구현 |
| **H1 자동 스케줄러** | ❌ [#7](https://github.com/SunhSOO/mtoss_bot/issues/7) |
| **확인 요청 영속화** | ❌ [#6](https://github.com/SunhSOO/mtoss_bot/issues/6) |
| **콘솔 실데이터** | ❌ [#14](https://github.com/SunhSOO/mtoss_bot/issues/14) — 지금은 목업 |

즉 지금 배포하면 **인프라와 배관을 미리 세워 두는 단계**다. 매매는 아직 하지 않는다.

---

## 1. 하드웨어·OS 준비

- Windows 11 또는 Windows Server, x64
- 메모리 8GB 이상 (MT5 터미널 + PostgreSQL + Node)
- **UPS 권장.** `order_send` 도중 정전은 실제로 일어난다. 선행기록이 복구를 *정확*하게 만들고, UPS가 복구를 *드물게* 만든다.

전원 설정 — 하나라도 빠지면 새벽에 조용히 멈춘다.

```powershell
# 절전·최대절전 해제
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /hibernate off

# 빠른 시작 해제 (재부팅 후 서비스가 제대로 뜨도록)
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" /v HiberbootEnabled /t REG_DWORD /d 0 /f
```

BIOS에서 **"정전 후 자동 복구(Restore on AC Power Loss)"** 를 켠다. 이건 OS에서 못 한다.

Windows Update가 아무 때나 재부팅하지 않도록 활성 시간을 지정한다.

---

## 2. 소프트웨어 설치

```powershell
winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
winget install --id astral-sh.uv -e --silent --accept-package-agreements --accept-source-agreements
winget install --id OpenJS.NodeJS.LTS -e --silent --accept-package-agreements --accept-source-agreements
winget install --id GitHub.cli -e --silent --accept-package-agreements --accept-source-agreements
winget install --id PostgreSQL.PostgreSQL.17 -e --silent --accept-package-agreements --accept-source-agreements `
  --override "--mode unattended --unattendedmodeui none --superpassword <강한-비밀번호> --serverport 5432 --disable-components stackbuilder"
```

설치 후 **PowerShell 창을 새로 연다.** 기존 창은 설치 전 PATH를 들고 있어 `uv`, `gh`를 못 찾는다.

MT5는 INFINOX 사이트에서 받아 설치한다 (winget에 없음).

> **Docker는 쓰지 않는다.** 저장소의 `compose.yaml`은 개발 편의용이다. Windows에서 Docker Desktop은 WSL2/Hyper-V를 요구하고 메모리를 먹으며, 자동 업데이트가 데이터베이스를 재시작시킨다.
> **PostgreSQL 버전**: 계획서는 16 기준이지만 winget에는 17/18만 있다. 우리가 쓰는 기능(JSONB, `FOR UPDATE SKIP LOCKED`, `NUMERIC`)은 동일해 17로 검증했다.

---

## 3. 저장소와 의존성

```powershell
git clone https://github.com/SunhSOO/mtoss_bot.git C:\mtoss
cd C:\mtoss
uv sync --all-groups --extra mt5      # --extra mt5 는 Windows에서만 동작
npm --prefix web install
```

---

## 4. 데이터베이스

```powershell
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$env:PGPASSWORD = "<위에서-정한-superpassword>"
& $psql -U postgres -h localhost -c "CREATE ROLE mtoss LOGIN PASSWORD '<DB-비밀번호>'"
& $psql -U postgres -h localhost -c "CREATE DATABASE mtoss OWNER mtoss"
$env:PGPASSWORD = $null
```

로컬 전용으로 잠근다. `C:\Program Files\PostgreSQL\17\data\postgresql.conf`:

```
listen_addresses = 'localhost'
```

`pg_hba.conf`에서 인증이 `scram-sha-256`인지 확인하고 서비스를 재시작한다.

```powershell
Restart-Service postgresql-x64-17
```

---

## 5. 설정 파일

```powershell
Copy-Item .env.example .env
```

`.env`를 열어 채운다.

```
DATABASE_URL=postgresql+asyncpg://mtoss:<DB-비밀번호>@localhost:5432/mtoss
INTERNAL_API_KEY=<긴-무작위-값>
```

무작위 키 생성:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Max 256 }))
```

**Redis는 설치하지 않는다.** 실행 경로는 PostgreSQL 아웃박스만 쓴다. `.env`의 `REDIS_URL` 줄은 주석 처리된 상태로 둔다 — 값이 있으면 헬스체크가 없는 서버에 접속을 시도해 503을 낸다.

마이그레이션 적용:

```powershell
uv run --env-file .env alembic upgrade head
```

---

## 6. MT5 설정

1. 터미널 실행 → `파일 → 거래계좌에 로그인`
   - 계좌 `87902957`, 서버 `InfinoxLimited-MT5Live`
   - **비밀번호 저장**을 체크해야 재부팅 후 자동 로그인된다
2. `도구 → 옵션 → 엑스퍼트 어드바이저` → **"알고리즘 거래 허용"** 체크
   - 이게 꺼져 있으면 주문이 전부 거부된다. 세션 시작 시 코드가 이를 감지해 멈춘다.
3. Market Watch에 **`XAUUSD+`** 를 추가한다

진단으로 확인:

```powershell
uv run --extra mt5 python ops/mt5_probe.py
```

주문은 내지 않고 조회만 한다. 다음을 확인하라.

- `terminal.trade_allowed = True`
- `margin_mode = RETAIL_HEDGING`
- `XAUUSD+` → `trade_mode = FULL`, `trade_contract_size = 100`, `filling_mode = IOC`
- `order_check` → `retcode=10009 Done`
- **장중에 다시 돌려 서버 시각 오프셋을 확인할 것.** 휴장 중에는 계산되지 않는다.

> 심볼 주의: `XAUUSD+` 가 신규 진입 가능한 유일한 금 심볼이다. `XAUUSD.m+`(10oz 마이크로)는 `CLOSEONLY`라 쓸 수 없다. 마이크로가 열리면 리스크가 1/10로 떨어지므로 INFINOX에 **마이크로 계좌 유형**을 문의해볼 가치가 있다.

---

## 7. 텔레그램

1. 텔레그램에서 **@BotFather** → `/newbot` → 이름과 `_bot`으로 끝나는 아이디 입력 → **토큰** 획득
2. 만들어진 봇과 대화를 열고 **`/start`** 전송
   — 텔레그램은 봇이 먼저 말을 걸 수 없다. 사용자가 대화를 시작해야 한다.
3. **@userinfobot** 에게 아무 메시지나 보내 본인 **chat_id** 확인
4. `.env`에 추가

```
TELEGRAM_BOT_TOKEN=<토큰>
TELEGRAM_CHAT_ID=<본인 chat_id>
```

`TELEGRAM_CHAT_ID`는 **보안 장치**다. 이 id에서 온 콜백만 받아들인다. 없으면 봇을 찾은 누구나 실계좌 진입 버튼을 누를 수 있어서, 토큰만 있고 chat_id가 없으면 설정 검증이 실패한다.

---

## 8. 서비스 등록

```powershell
winget install --id NSSM.NSSM -e --silent --accept-package-agreements --accept-source-agreements
```

일반 서비스로 띄울 수 있는 것:

```powershell
$uv = (Get-Command uv).Source

nssm install mtoss-api $uv "run --env-file .env uvicorn mtoss.api.app:create_app --factory --host 127.0.0.1 --port 8000"
nssm set mtoss-api AppDirectory C:\mtoss
nssm set mtoss-api Start SERVICE_AUTO_START
nssm set mtoss-api AppStdout C:\mtoss\logs\api.log
nssm set mtoss-api AppStderr C:\mtoss\logs\api.log
nssm start mtoss-api
```

`mtoss-executor`, `mtoss-strategy`, `mtoss-notify`, `mtoss-web`도 같은 방식으로 등록한다.

> API는 **`127.0.0.1`에 바인드한다.** 외부 노출은 nginx와 Cloudflare Tunnel이 담당한다.

### ⚠️ mt5node는 일반 서비스로 못 띄운다

MT5 터미널은 GUI 앱이라 **Session 0(일반 Windows 서비스)에서는 IPC가 실패**하고, 프로필이 빈 "유령 터미널"이 뜬다. 따라서 대화형 데스크톱 세션이 필요하다.

1. **자동 로그인** — Sysinternals `Autologon.exe` 사용 (레지스트리 평문 `DefaultPassword` 대신 LSA 암호화)
2. **작업 스케줄러** — 트리거 "로그온할 때", "사용자가 로그온한 경우에만 실행", "실패 시 1분마다 다시 시작"

이건 **자동 로그인이 보안 모델에 들어온다는 뜻**이다. 미니PC에 물리적으로 접근하면 실계좌에 접근하는 것과 같다. 상쇄 조치:

- **BitLocker 전체 디스크 암호화**
- 자동 로그인 직후 화면 잠금 — 세션은 대화형으로 유지되면서 화면만 잠긴다

```powershell
# 작업 스케줄러에 "로그온할 때" 트리거로 함께 등록
rundll32.exe user32.dll,LockWorkStation
```

---

## 9. 외부 접속

**포트포워딩은 하지 않는다.** 이 박스는 집 LAN을 개인 기기와 공유한다.

nginx를 로컬 리버스 프록시로 둔다.

```nginx
server {
    listen 127.0.0.1:8080;
    location /          { proxy_pass http://127.0.0.1:3100; }  # Next 콘솔
    location /internal  { proxy_pass http://127.0.0.1:8000; }  # FastAPI
}
```

Cloudflare Tunnel로 내보낸다 — **아웃바운드 전용이라 개방 포트가 0개다.**

```powershell
winget install --id Cloudflare.cloudflared -e --silent --accept-package-agreements --accept-source-agreements
cloudflared tunnel login
cloudflared tunnel create mtoss
# config.yml에서 tunnel → http://127.0.0.1:8080 으로 매핑
cloudflared service install
```

**Cloudflare Access를 반드시 켠다.** Zero Trust → Access → Applications에서 터널 호스트명에 정책을 걸고 본인 이메일만 허용한다.

> ⚠️ **Access 없이 노출하면 안 된다.** 현재 콘솔은 역할을 `?role=` 쿼리에서 읽고 **기본값이 `ADMIN`**이다 ([#15](https://github.com/SunhSOO/mtoss_bot/issues/15)). URL을 아는 누구나 실계좌 관리자가 된다.

텔레그램 롱폴링도 아웃바운드만 쓰므로 이 구성과 충돌하지 않는다.

---

## 10. 백업

```powershell
New-Item -ItemType Directory -Force C:\mtoss\backups | Out-Null
& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -U mtoss -h localhost -d mtoss `
  --format=custom --file="C:\mtoss\backups\mtoss-$(Get-Date -Format yyyyMMdd).dump"
```

작업 스케줄러로 매일 실행하고 **다른 디스크와 박스 외부**로 복사한다.

**복구를 실제로 테스트하기 전에는 백업이 아니다.** 일회용 DB에 복원해 보고 마이그레이션이 통과하는지 확인하라.

---

## 11. 설치 검증

```powershell
cd C:\mtoss
uv run --env-file .env pytest tests -v
uv run ruff check .
uv run mypy src/mtoss
npm --prefix web run build
```

마이그레이션 왕복 (일회용 DB만 삭제한다):

```powershell
$psql = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
$env:PGPASSWORD = "<superpassword>"
& $psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS mtoss_ci_verify"
& $psql -U postgres -h localhost -c "CREATE DATABASE mtoss_ci_verify OWNER mtoss"
$env:PGPASSWORD = $null
$env:DATABASE_URL = "postgresql+asyncpg://mtoss:<DB-비밀번호>@localhost:5432/mtoss_ci_verify"
uv run --env-file .env alembic upgrade head
uv run --env-file .env alembic downgrade base
uv run --env-file .env alembic upgrade head
$env:DATABASE_URL = $null
```

헬스체크:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

재부팅 후에도 전부 살아나는지 확인한다 — 이게 "항상 켜 둔다"의 실제 의미다.

```powershell
Restart-Computer
# 부팅 후: 서비스 상태, MT5 자동 로그인, 터널 연결, 헬스체크
```

---

## 12. 실계좌 전 필수 항목

여기까지는 인프라다. **실주문을 켜기 전에 아래가 전부 있어야 한다.**

| | 항목 | 이유 |
|---|---|---|
| [#4](https://github.com/SunhSOO/mtoss_bot/issues/4) | MT5 어댑터 본체 | 주문을 보낼 수단 자체 |
| [#5](https://github.com/SunhSOO/mtoss_bot/issues/5) | 링크 저장소 (PostgreSQL) | 중복주문 방지 |
| [#9](https://github.com/SunhSOO/mtoss_bot/issues/9) | `expires_at` 검사 | 몇 시간 지난 신호가 그대로 나가는 것 방지 |
| [#10](https://github.com/SunhSOO/mtoss_bot/issues/10) | 정합성 조정기 | `UNKNOWN` 해소 |
| [#11](https://github.com/SunhSOO/mtoss_bot/issues/11) | 긴급정지 | 멈출 방법 |
| [#12](https://github.com/SunhSOO/mtoss_bot/issues/12) | 리스크 룰 시드 | 없으면 모든 주문이 조용히 거부됨 |
| [#13](https://github.com/SunhSOO/mtoss_bot/issues/13) | 승인 엔드포인트 | MANUAL 모드가 막다른 길 |
| [#15](https://github.com/SunhSOO/mtoss_bot/issues/15) | 콘솔 인증 | 외부 노출 전 필수 |
| — | 복구가 검증된 백업 | |

그리고 순서대로: **FakeBroker → MT5 데모(`MT5_SUBMIT_ENABLED=false` 섀도) → 데모 실주문 + 카오스 테스트 → 실계좌 최소랏.**

### 이 계좌에서 알고 있어야 할 숫자

자본 $389.57, `XAUUSD+`는 100oz 계약이라 **0.01랏 = 1oz**다. 손절 시 손실이 곧 R달러다.

| R (손절폭) | 적용 랏 | 2트랜치 손실 | 자본 대비 |
|---|---|---|---|
| $10 | 0.02 | $40 | 10% |
| $25 | 0.01 | $50 | 13% |
| $39 초과 | 0.01 | $78+ | 20%+ → **확인 요청** |

레버리지가 1:1000이라 증거금은 전혀 제약이 아니다(0.04랏에 $18). **브로커가 막아 주지 않는다는 뜻**이고, `max_lots = 0.02` 상한이 유일한 브레이크다.

최소 거래 단위가 이미 예산 근처라 리스크% 사이징이 수량을 줄일 여지가 거의 없다. 실제로는 수량 조절기가 아니라 **예산 초과 시 확인을 요청하는 게이트**로 동작한다.
