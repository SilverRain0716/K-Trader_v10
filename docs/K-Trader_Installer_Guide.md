# K-Trader 인스톨러 제작 가이드

> Windows PC에서 `K-Trader_Setup_v7.5.exe` 인스톨러를 만드는 전체 과정입니다.
> 총 소요시간: 약 30~60분 (대부분 다운로드/설치 대기)

---

## 전체 흐름 요약

```
[준비] Python 32비트 설치
  ↓
[준비] 앱 아이콘 준비 (.ico)
  ↓
[Step 1] build.bat 실행 → K-Trader.exe 생성
  ↓
[Step 2] K-Trader.exe 테스트 실행
  ↓
[Step 3] Inno Setup 설치
  ↓
[Step 4] installer.iss 컴파일 → K-Trader_Setup_v7.5.exe 완성
```

---

## 준비물 체크리스트

| 항목 | 필수 여부 | 설명 |
|------|-----------|------|
| Windows 10/11 PC | ✅ 필수 | 빌드 환경 |
| Python 3.8~3.12 (32비트) | ✅ 필수 | 키움 OpenAPI가 32비트 전용 |
| K-Trader 소스 폴더 | ✅ 필수 | 다운로드한 K-Trader/ 폴더 전체 |
| 앱 아이콘 (.ico) | 선택 | 없으면 기본 Python 아이콘 사용 |
| Inno Setup 6 | ✅ 필수 | 인스톨러 생성 도구 (무료) |
| 인터넷 연결 | ✅ 필수 | pip 패키지 다운로드용 |

---

## 준비 단계: Python 32비트 설치

### 이미 Python이 있는 경우 — 비트 확인

명령 프롬프트(cmd)를 열고:

```
python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
```

**32 bit** 이 나오면 → 바로 Step 1로 진행
**64 bit** 이 나오면 → 아래 절차대로 32비트 설치

### 32비트 Python 새로 설치

1. https://www.python.org/downloads/ 접속

2. 최신 Python 3.12.x 클릭 → 하단 **Files** 섹션에서:
   - ❌ `Windows installer (64-bit)` ← 이거 아님!
   - ✅ **`Windows installer (32-bit)`** ← 이걸 다운로드

3. 다운로드한 `python-3.12.x.exe` 실행

4. **⚠️ 중요: 첫 화면 하단의 체크박스 2개 모두 체크:**
   - ☑ `Install launcher for all users`
   - ☑ **`Add Python 3.12 to PATH`** ← 반드시!

5. **"Install Now"** 클릭 (기본 설정으로 충분)

6. 설치 완료 후 cmd를 **새로** 열어서 확인:

```
python --version
python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
```

`Python 3.12.x` + `32 bit` 이 나오면 성공.

### ⚠️ 64비트와 32비트 Python이 둘 다 있는 경우

PATH에서 32비트가 먼저 오도록 해야 합니다:

1. 시작 메뉴 → "환경 변수" 검색 → "시스템 환경 변수 편집"
2. "환경 변수" 버튼 클릭
3. "Path" 선택 → "편집"
4. Python 32비트 경로를 맨 위로 이동:
   - 예: `C:\Users\사용자\AppData\Local\Programs\Python\Python312-32\`
   - 그 아래: `C:\Users\사용자\AppData\Local\Programs\Python\Python312-32\Scripts\`
5. 확인 후 cmd를 **새로** 열어서 다시 확인

---

## 준비 단계: 앱 아이콘 (.ico)

인스톨러와 EXE에 사용할 아이콘 파일이 필요합니다.

### 방법 1: 직접 만들기
- 아무 이미지(256×256 이상 PNG 권장)를 https://convertio.co/png-ico/ 에서 .ico로 변환
- 또는 https://favicon.io/ 에서 텍스트 기반 아이콘 생성

### 방법 2: 무료 아이콘 다운로드
- https://icon-icons.com/ 에서 "trading" 또는 "chart" 검색
- .ico 형식으로 다운로드

### 아이콘 배치
다운로드한 `icon.ico` 파일을:

```
K-Trader/
  └── assets/
       └── icon.ico    ← 여기에 복사
```

> 아이콘이 없어도 빌드는 됩니다. 다만 기본 Python 아이콘이 사용됩니다.

---

## Step 1: build.bat 실행 (EXE 빌드)

### 1-1. K-Trader 폴더를 원하는 위치에 복사

예시:
```
C:\Projects\K-Trader\
  ├── main.py
  ├── build.bat
  ├── requirements.txt
  ├── installer.iss
  ├── src\
  │   ├── engine.py
  │   ├── ui_dashboard.py
  │   └── ... (14개 파일)
  ├── assets\
  │   └── icon.ico (선택)
  └── docs\
      └── K-Trader_Guide.pdf
```

### 1-2. build.bat 실행

**방법 A**: 탐색기에서 `build.bat` 더블클릭

**방법 B**: 명령 프롬프트에서:
```
cd C:\Projects\K-Trader
build.bat
```

### 1-3. 빌드 진행 과정 (자동)

```
[0/5] Python 환경 확인...         ← 32비트 확인
  [OK] 32-bit Python 확인 완료

[1/5] pip 의존성 설치 중...       ← PyQt5, requests 등 설치
  [OK] 의존성 설치 완료

[2/5] 아이콘 파일 발견             ← icon.ico 있으면 표시

[3/5] K-Trader.exe 빌드 중...     ← 1~3분 소요 (가장 오래 걸림)
  [OK] K-Trader.exe 빌드 완료

[4/5] Setup Wizard 빌드 중...     ← 30초 소요
  [OK] Setup Wizard 빌드 완료

[5/5] 배포 폴더 구성 중...        ← 빈 폴더 + PDF 복사
  [OK] 완료
```

### 1-4. 빌드 결과물 확인

```
K-Trader/
  └── dist/
       └── K-Trader/                     ← 이 폴더 전체가 배포 대상
            ├── K-Trader.exe              ← 메인 프로그램
            ├── K-Trader Setup Wizard.exe ← 설정 마법사
            ├── config/                   ← 빈 폴더 (설정 자동 생성)
            ├── data/
            ├── logs/
            ├── reports/
            ├── docs/
            │    └── K-Trader_Guide.pdf
            ├── src/                      ← 소스 파일 (PyInstaller가 포함)
            ├── PyQt5/                    ← PyQt5 DLL들
            ├── python312.dll             ← Python 런타임
            └── ... (기타 DLL/pyd 파일들)
```

### ⚠️ 빌드 에러 발생 시

| 에러 | 원인 | 해결 |
|------|------|------|
| `64비트 Python 감지` | Python이 64비트 | 32비트 Python 설치 |
| `ModuleNotFoundError: PyQt5` | pip 설치 실패 | `pip install PyQt5` 수동 실행 |
| `No module named 'src.engine'` | hidden-import 누락 | build.bat이 이미 처리함 — 경로 확인 |
| `Permission denied` | 안티바이러스 차단 | Windows Defender에서 K-Trader 폴더 제외 |

---

## Step 2: 빌드된 EXE 테스트

인스톨러를 만들기 **전에** 먼저 EXE가 정상 작동하는지 확인합니다.

### 2-1. K-Trader.exe 실행

```
dist\K-Trader\K-Trader.exe
```

를 더블클릭합니다.

### 2-2. 첫 실행 시 확인 사항

1. **설정 마법사**가 자동으로 뜨는지 확인
   - secrets 파일이 없으므로 자동 실행됩니다
   - 마법사에서 키움 API 확인 → 비밀번호 → 웹훅 입력
   - "완료" 누르면 `config/secrets.json` 생성

2. **메인 UI**가 정상적으로 뜨는지 확인
   - 키움 로그인 화면이 나오면 정상
   - 타이틀바에 "K-Trader Master" 표시

3. **설정 마법사 단독 실행** 확인
   ```
   dist\K-Trader\K-Trader Setup Wizard.exe
   ```
   를 별도로 실행해서 정상 작동 확인

### 2-3. 문제가 있으면

- `dist\K-Trader\` 폴더 안에서 cmd를 열고:
  ```
  K-Trader.exe
  ```
  실행하면 콘솔에 에러 메시지가 표시됩니다.

---

## Step 3: Inno Setup 설치

### 3-1. 다운로드

https://jrsoftware.org/isdl.php 접속

**"Inno Setup 6.x"** 의 `innosetup-6.x.x.exe` 다운로드
(가장 위에 있는 것이 최신 안정 버전)

### 3-2. 설치

1. 다운로드한 `innosetup-6.x.x.exe` 실행
2. 언어: **English** (한국어 없음, 영어로 설치)
3. 설치 경로: 기본값 유지 (`C:\Program Files (x86)\Inno Setup 6`)
4. **⚠️ "Install Inno Setup Preprocessor" 체크 확인** (기본 체크됨)
5. Install → 완료

### 3-3. 한국어 언어 파일 확인

Inno Setup 설치 폴더의 `Languages\` 폴더에:
```
C:\Program Files (x86)\Inno Setup 6\Languages\Korean.isl
```
파일이 있는지 확인합니다. 보통 기본 포함되어 있습니다.

**없으면**: https://raw.githubusercontent.com/jrsoftware/issrc/main/Files/Languages/Unofficial/Korean.isl 에서 다운로드 → `Languages\` 폴더에 복사

---

## Step 4: 인스톨러 생성

### 4-1. installer.iss 열기

**방법 A**: 탐색기에서 `installer.iss` 파일을 더블클릭
→ Inno Setup Compiler가 자동으로 열립니다

**방법 B**: Inno Setup Compiler를 먼저 실행 → File → Open → `installer.iss` 선택

### 4-2. installer.iss 내용 확인

열린 파일에서 경로가 맞는지 확인합니다:

```ini
[Setup]
AppName=K-Trader Master
AppVersion=7.5
OutputBaseFilename=K-Trader_Setup_v7.5      ← 생성될 인스톨러 파일명
SetupIconFile=assets\icon.ico               ← 아이콘 (없으면 이 줄 삭제)

[Files]
Source: "dist\K-Trader\*"; ...              ← build.bat 결과물 경로
Source: "dist\K-Trader Setup Wizard.exe"    ← 설정 마법사
Source: "docs\K-Trader_Guide.pdf"           ← 가이드 PDF
```

**⚠️ 아이콘 파일이 없는 경우:**
`SetupIconFile=assets\icon.ico` 줄을 삭제하거나 앞에 세미콜론(;)을 붙여 주석처리:
```ini
;SetupIconFile=assets\icon.ico
```

### 4-3. 컴파일 실행

메뉴에서: **Build → Compile** (또는 `Ctrl+F9`)

```
Compiler Output:
  Reading script...
  Compiling...
  Compression: lzma2
  Output filename: K-Trader_Setup_v7.5.exe
  ...
  Compile completed.
```

### 4-4. 결과물 확인

```
K-Trader/
  └── Output/
       └── K-Trader_Setup_v7.5.exe    ← 인스톨러 완성!
```

파일 크기는 약 **30~80 MB** 정도입니다.
(Python 런타임 + PyQt5 DLL + 소스 코드 포함)

### ⚠️ 컴파일 에러 발생 시

| 에러 | 원인 | 해결 |
|------|------|------|
| `Source file not found: dist\K-Trader\*` | build.bat 미실행 | Step 1 먼저 실행 |
| `Source file not found: assets\icon.ico` | 아이콘 없음 | 해당 줄 삭제 또는 아이콘 추가 |
| `Source file not found: docs\K-Trader_Guide.pdf` | PDF 없음 | docs 폴더에 PDF 복사 |
| `Korean.isl not found` | 한국어 파일 없음 | Step 3-3 참조 |

---

## Step 5: 인스톨러 테스트

### 5-1. 다른 PC에서 테스트 (권장)

가능하면 빌드하지 않은 **다른 Windows PC**에서 테스트합니다:

1. `K-Trader_Setup_v7.5.exe` 를 USB 등으로 복사
2. 더블클릭하여 설치
3. 설치 과정:
   - 설치 경로 선택 (기본: `C:\Program Files\K-Trader`)
   - "바탕화면에 바로가기 생성" 체크
   - "설치" 클릭
   - 설치 완료 → "설정 마법사 실행" 체크 → "마침"

4. 확인 사항:
   - 바탕화면에 "K-Trader Master" 아이콘이 생기는지
   - 시작 메뉴에 "K-Trader Master" 폴더가 생기는지
   - 설정 마법사가 정상 작동하는지
   - 메인 프로그램이 정상 실행되는지
   - "프로그램 추가/제거"에서 제거가 되는지

### 5-2. 같은 PC에서 테스트

다른 PC가 없으면 같은 PC에서도 테스트 가능합니다:
1. 인스톨러 실행 → 설치 경로를 `C:\Test\K-Trader` 등으로 변경
2. 설치 후 실행 테스트
3. 테스트 완료 후 "프로그램 추가/제거"에서 제거

---

## 최종 체크리스트

- [ ] Python 32비트 설치 확인
- [ ] build.bat 실행 → dist\K-Trader\ 생성 확인
- [ ] K-Trader.exe 단독 실행 테스트 통과
- [ ] K-Trader Setup Wizard.exe 단독 실행 테스트 통과
- [ ] Inno Setup 6 설치
- [ ] installer.iss 경로 확인 (아이콘 없으면 줄 삭제)
- [ ] Build → Compile → Output\K-Trader_Setup_v7.5.exe 생성
- [ ] 인스톨러 실행 테스트 → 설치 → 실행 → 제거 확인

---

## 배포 시 안내 사항

인스톨러를 다른 사람에게 배포할 때 함께 안내할 내용:

1. **키움 OpenAPI는 별도 설치 필요** — 인스톨러에 포함되지 않음
2. **키움증권 계좌 필요** — 모의투자라도 계좌 개설 필요
3. **32비트 환경** — 이미 Python 환경은 EXE에 포함되어 있으므로 사용자가 Python을 설치할 필요 없음
4. **첫 실행 시 설정 마법사** — 비밀번호, 디스코드 웹훅 등을 입력
5. **Windows 전용** — macOS, Linux에서는 사용 불가 (키움 OpenAPI 제약)
