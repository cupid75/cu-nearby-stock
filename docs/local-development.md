# 개발·실행·배포 안내

## 처음 설치하기

배포 설정과 같은 Python 3.14를 기준으로 합니다. 저장소 최상위 폴더에서 실행하세요.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt`는 실행용, `requirements-dev.txt`는 자동 검사와 연결 확인 도구까지 사용할 때 필요합니다. 가상환경은 이 프로젝트 전용 패키지 보관 폴더이며 GitHub에 올리지 않습니다.

## Windows에서 실행하기

```powershell
.\.venv\Scripts\python.exe local_server.py
```

키가 없으면 숨김 입력으로 카카오 JavaScript 키를 받습니다. 키는 서버 프로세스의 환경 변수로만 전달합니다. [http://127.0.0.1:8000](http://127.0.0.1:8000)에 접속하세요.

```powershell
.\.venv\Scripts\python.exe local_server.py --check
.\.venv\Scripts\python.exe local_server.py --stop
```

실행기를 종료해도 서버는 계속 실행됩니다. `--stop`은 실행기가 기록한 서버만 종료합니다. 다른 프로그램이 8000번 포트를 사용하면 자동 종료하지 않습니다. 키를 바꾸려면 서버를 종료하고 다시 실행하세요. 키 없이 확인하려면 `--without-key`를 붙입니다.

## 터미널에서 직접 실행하기

Windows 개발용 명령입니다. 종료하려면 Ctrl+C를 누릅니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

macOS·Linux에서는 다음 명령을 사용합니다. 지도용 키는 실행 전에 `KAKAO_JS_KEY` 환경 변수에 설정해야 합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Windows 실행기 외의 키 입력 방식은 사용하는 터미널의 안전한 입력 기능을 사용하세요. 실제 키를 소스나 명령 예제에 적어 커밋하지 않습니다. `.env` 자동 로딩은 구현하지 않았습니다.

## 지도와 환경 변수

[카카오 개발자 사이트](https://developers.kakao.com/)에서 앱의 카카오맵 사용을 활성화하고 JavaScript 키의 허용 도메인에 로컬 주소를 등록합니다. 로컬은 `http://127.0.0.1:8000`, 필요하면 `http://localhost:8000`도 추가합니다. 배포 후에는 실제 HTTPS 사이트 주소를 추가합니다.

| 변수 | 용도 | 설정 기준 |
|---|---|---|
| `KAKAO_JS_KEY` | 지도와 장소 검색 | JavaScript 키 사용. REST API 키·Admin 키와 다름 |
| `SESSION_SECRET` | 익명 세션 쿠키 서명 | 공개 서버는 충분히 긴 임의 문자열. 로컬 미설정 시 실행마다 자동 생성 |
| `COOKIE_SECURE` | HTTPS에서만 쿠키 전송 | 공개 HTTPS는 `1`, 로컬 HTTP는 미설정 |
| `PYTHON_VERSION` | Render Python 버전 | `render.yaml`에 `3.14.0` 지정 |

JavaScript 키는 브라우저가 지도를 불러올 때 전달되므로 허용 도메인을 제한해야 합니다. `SESSION_SECRET`은 브라우저에 공개하지 않습니다. 키가 없어도 상품 검색 API와 재고 목록 기능은 사용할 수 있지만 지도와 동네 검색은 작동하지 않습니다.

## 검사

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

자동 검사는 CU 응답을 가짜 데이터로 바꿔 상태 구분·반경·거리 정렬·캐시·요청 제한·오류 처리를 확인합니다. 외부 CU 연결 성공을 뜻하지는 않습니다.

화면 검사 전용 서버:

```powershell
.\.venv\Scripts\python.exe -m uvicorn tests.ui_fixture_server:app --host 127.0.0.1 --port 8001 --no-access-log
```

[가상 화면](http://127.0.0.1:8001)과 [가상 위치 거절 화면](http://127.0.0.1:8001/?scenario=denied)을 제공합니다. 실제 위치·재고가 아니며 이 서버를 공개 배포에 사용하면 안 됩니다.

실제 CU 연결 확인은 별도 명령으로 한 번 실행합니다. 고정된 서울시청 예시 좌표와 상품을 사용하며 사용자 주변 재고가 아닙니다. 오류가 나면 자동 반복하지 않습니다.

```powershell
.\.venv\Scripts\python.exe verify_live.py
.\.venv\Scripts\python.exe verify_live.py --base-url https://cu-nearby-stock.onrender.com
```

첫 명령은 로컬 서버 코드를 직접 검사하므로 실행 중인 8000번 서버가 필요하지 않습니다. 두 번째 명령은 배포된 서버를 검사합니다. 원문 결과를 파일에 저장하지 않고 요약만 출력합니다.

## Render 배포

GitHub 저장소를 연결하고 `render.yaml`을 사용하는 Blueprint로 배포하거나 다음 값으로 Web Service를 설정합니다. 계정 로그인·저장소 접근 허용·키 입력은 본인 계정에서 진행합니다.

| 항목 | 설정 |
|---|---|
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log` |
| Health check | `/health` |
| 환경 변수 | 위 표 참고. Blueprint는 `SESSION_SECRET` 자동 생성, `KAKAO_JS_KEY` 직접 입력 |

`render.yaml`은 Free 요금제를 지정합니다. 실제 제공 조건은 배포 시 계정 화면에서 확인하세요. 개발용 패키지는 운영 서버에 설치할 필요가 없습니다. 배포 후 카카오 허용 도메인을 추가하고 공개 서버에서 지도·상품 검색·재고 연결을 확인합니다. PC에서의 성공만으로 배포 서버 성공을 판단하지 않습니다.

캐시와 요청 제한은 서버 메모리에 있으므로 `--workers 1`을 유지합니다. `--no-access-log`는 요청 접근 로그를 끄는 설정입니다.
