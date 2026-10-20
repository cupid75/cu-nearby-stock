# CU 근처 재고 찾기

**“나도 리센느 빵 사먹고 싶다!”**

원하는 상품을 찾아 여러 CU 매장을 돌아다니는 수고를 줄이고자 만든 모바일 웹 서비스입니다.

👉 [서비스 이용하기](https://cu-nearby-stock.onrender.com/)

## 구현 목적

리센느 빵을 사고 싶었지만, 어느 매장에 재고가 있는지 미리 알기 어려웠습니다. 이 불편을 해결하기 위해 **상품 검색부터 주변 매장의 재고 확인까지 이어지는 서비스**를 만들었습니다.

휴대폰에서 간편하게 사용할 수 있도록 검색 화면과 재고 결과 화면을 나눴습니다. 리센느 빵과 맛피아 상품은 빠른검색 버튼으로 바로 확인할 수 있습니다.

사실은 리센느 포토카드가 갖고싶은 리센느 팬 입니다;;

## 주요 기능

- **상품 검색:** 상품명을 입력하고 원하는 상품 선택
- **빠른검색:** 리센느·맛피아 상품을 버튼 한 번으로 검색
- **위치 선택:** 현재 위치 확인 또는 동네·역 이름 검색
- **주변 재고 확인:** 반경 1·2·5km 내 조회된 매장을 지도와 가까운 순 목록으로 표시
- **매장 상세:** 재고 수량, 주소, 직선거리, 조회 시각, 카카오맵 길찾기 제공
- **조회 단계 간소화:** 위치가 지정되어 있으면 상품 선택 후 재고 자동 조회

## 사용 기술

| 구분 | 기술 및 활용 |
|---|---|
| 서버 | **Python · FastAPI** — 상품 검색·매장 재고 조회 API |
| 화면 | **HTML · CSS · JavaScript** — 모바일 중심 화면과 화면 전환 |
| 지도 | **Kakao Maps JavaScript SDK** — 지도, 매장 마커, 장소 검색 |
| 위치 | **브라우저 위치 API** — 버튼을 눌렀을 때 현재 위치 확인 |
| 배포 | **Render** — 웹 화면과 API 서버 함께 운영 |
| 코드 관리 | **GitHub** — 소스 관리 및 배포 연동 |

## 구현 과정에서 고려한 점

- **쉬운 사용 흐름:** 상품 선택 → 위치 확인 → 주변 재고 확인으로 단계를 구성했습니다.
- **상태를 구분하는 안내:** 재고 있음·품절·수량 미확인·연결 오류를 구분해 표시했습니다.
- **불필요한 요청 줄이기:** 상품 검색은 10분, 동일 상품·좌표의 재고는 30초 동안 캐시하며, 익명 브라우저 기준 분당 10회로 요청을 제한했습니다.
- **위치정보 최소 사용:** 위치는 버튼을 누를 때 한 번 확인하며, 지속 추적하거나 파일·DB에 저장하지 않습니다.
- **피드백 기반 개선:** 실제 사용 피드백을 반영해 화면 분리, 작은 빠른검색 태그, 선택 안내 강조, 지도 마커 디자인 등을 개선했습니다.

## 이용 안내

CU 공식 서비스가 아닌 개인 프로젝트입니다. CU가 반환한 매장만 조회하며, 재고는 실시간으로 달라질 수 있습니다. 방문 전 매장에 확인해 주세요.

무료 서버로 운영되어 첫 접속 시 화면이 열리기까지 시간이 걸릴 수 있습니다.

## 실행 방법

Python 3.14와 Git이 필요합니다. Windows PowerShell 기준입니다.

```powershell
git clone https://github.com/cupid75/cu-nearby-stock.git
cd cu-nearby-stock
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe local_server.py
```

실행 중 카카오 **JavaScript 키** 입력 안내가 나오면 키를 입력합니다. 입력 글자는 표시되지 않으며 파일에 저장하지 않습니다. 준비가 끝나면 [로컬 사이트](http://127.0.0.1:8000)에 접속합니다. 지도·동네 검색을 사용하려면 카카오맵 사용 설정과 허용 도메인 등록도 필요합니다.

키 없이 상품 검색·화면을 확인하려면 마지막 명령을 다음으로 바꿉니다. 지도와 동네 검색은 사용할 수 없습니다.

```powershell
.\.venv\Scripts\python.exe local_server.py --without-key
```

Windows 실행기는 터미널을 닫아도 서버를 유지합니다. 종료할 때는 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe local_server.py --stop
```

다른 운영체제의 실행 방법, 키 설정, 검사와 배포 방법은 [개발·실행 안내](docs/local-development.md)를 참고하세요. `.env` 파일을 자동으로 읽는 기능은 없습니다.

## 파일 구성

```text
app.py                       # 웹 서버, 재고 API, 캐시·요청 제한
cu_stock_check.py            # 서버에서도 재사용하는 CU 요청 함수
static/                     # HTML, CSS, JavaScript, 로고
requirements.txt            # 실행에 필요한 Python 패키지
requirements-dev.txt        # 검사에 필요한 추가 패키지
render.yaml                 # Render 배포 설정
local_server.py              # Windows 실행·상태 확인·종료
verify_live.py               # 실제 CU 연결 확인 도구
tests/                      # 자동 검사와 가상 화면 검사 서버
docs/                       # 실행·설계·문제 해결 설명
.gitignore                  # 키·설치 파일·임시 파일 제외 규칙
```

## 설명 문서

- [개발·실행·배포 방법](docs/local-development.md)
- [설계 이유와 데이터 처리 방식](docs/architecture.md)
- [해결한 문제와 개선 과정](docs/development-notes.md)

## 사이트 주소

[CU 근처 재고 찾기 이용하기](https://cu-nearby-stock.onrender.com/)
