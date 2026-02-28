"""
K-Trader v6.0 - 설정 & 시크릿 관리
[개선 #2]  secrets.json 암호화 (Fernet 대칭키)
[개선 #18] 조건식별 독립 파라미터 지원
"""
import os
import json
import logging
import base64
import hashlib
import getpass
import socket
import copy

logger = logging.getLogger("ktrader")

# cryptography는 선택적 의존성 — 없으면 base64 난독화로 대체
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.info("[보안] cryptography 미설치 → base64 난독화 모드 (pip install cryptography 로 업그레이드 가능)")


# ============================================================
# 시크릿 암호화 관리자 (개선 #2)
# ============================================================
class SecretManager:
    """
    secrets.json 보호.
    - cryptography 설치 시: Fernet 대칭키 암호화
    - 미설치 시: base64 난독화 (평문보다 안전)
    최초 실행 시 평문 → 보호 파일로 자동 마이그레이션.
    """

    def __init__(self, config_dir: str):
        self.secrets_path = os.path.join(config_dir, "secrets.json")
        self.encrypted_path = os.path.join(config_dir, "secrets.enc")
        self._key = self._derive_key()
        if HAS_CRYPTO:
            self._fernet = Fernet(self._key)

    @staticmethod
    def _derive_key() -> bytes:
        """
        암호화 키 파생.
        우선순위:
          1) 환경변수 KTRADER_FERNET_KEY (Fernet 키: urlsafe base64(32 bytes))
          2) 환경변수 KTRADER_SECRET_SEED (임의 문자열 → SHA256 → Fernet 키)
          3) 기존 방식(유저명@호스트명 기반) — 같은 PC에서는 안정적이나, 다른 PC로 옮기면 복호화 불가
        """
        # 1) 사용자가 직접 제공한 Fernet 키를 우선 사용
        env_key = os.getenv("KTRADER_FERNET_KEY", "").strip()
        if env_key:
            try:
                raw = base64.urlsafe_b64decode(env_key.encode("utf-8"))
                if len(raw) == 32:
                    return base64.urlsafe_b64encode(raw)
                logger.warning("⚠️ [보안] KTRADER_FERNET_KEY 형식이 올바르지 않습니다 (32바이트 키 필요).")
            except Exception:
                logger.warning("⚠️ [보안] KTRADER_FERNET_KEY 디코딩 실패. 기본 키 파생을 사용합니다.")

        # 2) 시드 문자열 기반 (서버/PC 이동 시에도 동일 시드를 쓰면 복호화 가능)
        seed_override = os.getenv("KTRADER_SECRET_SEED", "").strip()
        if seed_override:
            digest = hashlib.sha256(seed_override.encode("utf-8")).digest()
            return base64.urlsafe_b64encode(digest)

        # 3) 머신 고유 시드 기반(레거시)
        user = getpass.getuser()
        host = socket.gethostname()
        seed = f"{user}@{host}_ktrader_v6"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    
    @staticmethod
    def _load_json_lenient(path: str) -> dict:
        """
        JSON 로드를 최대한 관대하게 수행합니다.
        - 정상 JSON이면 그대로 로드
        - 파일 끝에 설명 문장/주석이 붙어 JSONDecodeError가 나면,
          마지막 '}' 또는 ']' 이후를 잘라내고 재시도
        """
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                raw = f.read().strip()
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # trailing text(설명/주석) 제거 시도
                last_obj = raw.rfind("}")
                last_arr = raw.rfind("]")
                cut = max(last_obj, last_arr)
                if cut != -1:
                    try:
                        return json.loads(raw[:cut + 1])
                    except Exception:
                        pass
                raise
        except Exception as e:
            logger.error(f"❌ [보안] JSON 로드 실패: {path} ({e})")
            return {}
    def _encrypt(self, raw: bytes) -> bytes:
        if HAS_CRYPTO:
            return self._fernet.encrypt(raw)
        # 폴백: XOR 난독화 + base64
        key_bytes = self._key
        xored = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw))
        return base64.b64encode(xored)

    def _decrypt(self, data: bytes) -> bytes:
        if HAS_CRYPTO:
            return self._fernet.decrypt(data)
        # 폴백: base64 디코드 + XOR 복원
        key_bytes = self._key
        xored = base64.b64decode(data)
        return bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(xored))

    def load(self) -> dict:
        """시크릿 로드. 평문 파일이 있으면 자동 마이그레이션."""
        # 1) 평문 파일이 남아있으면 마이그레이션
        if os.path.exists(self.secrets_path):
            logger.info("[보안] 평문 secrets.json 감지 → 보호 파일로 마이그레이션")
            try:
                data = self._load_json_lenient(self.secrets_path)
                
                # 저장이 완벽하게 성공했을 때만 원본을 삭제하여 데이터 증발 방지
                if self.save(data):
                    os.remove(self.secrets_path)
                    mode = "Fernet 암호화" if HAS_CRYPTO else "base64 난독화"
                    logger.info(f"✅ [보안] 마이그레이션 완료 ({mode}). 평문 삭제됨.")
                else:
                    logger.warning("⚠️ [보안] 암호화 파일 생성에 실패하여 평문 파일을 유지합니다.")
                
                return data
            except Exception as e:
                logger.error(f"❌ [보안] 마이그레이션 실패: {e}")
                # 마이그레이션 실패 시 평문이라도 읽기
                try:
                    return self._load_json_lenient(self.secrets_path)
                except:
                    return {}

        # 2) 보호된 파일 로드
        if os.path.exists(self.encrypted_path):
            try:
                with open(self.encrypted_path, "rb") as f:
                    encrypted = f.read()
                decrypted = self._decrypt(encrypted)
                return json.loads(decrypted.decode("utf-8"))
            except Exception as e:
                logger.error(f"❌ [보안] secrets.enc 복호화 실패: {e}")
                return {}

        logger.warning("⚠️ [보안] 시크릿 파일이 없습니다. config/secrets.json을 생성해주세요.")
        return {}

    def save(self, data: dict) -> bool:
        """시크릿을 보호하여 저장. 성공 여부를 반환."""
        try:
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            encrypted = self._encrypt(raw)
            with open(self.encrypted_path, "wb") as f:
                f.write(encrypted)
            # 가능한 OS에서는 권한을 최소화(소유자 읽기/쓰기)합니다.
            try:
                os.chmod(self.encrypted_path, 0o600)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"❌ [보안] 시크릿 저장 실패: {e}")
            return False


# ============================================================
# 봇 설정 관리자 (개선 #18: 조건식별 독립 파라미터)
# ============================================================
DEFAULT_CONFIG = {
    # 글로벌 설정
    "invest_type": "비중(%)",
    "invest": 20,
    "max_hold": 5,
    "max_loss": 50000,
    "timecut": True,
    "shutdown_opt": "프로그램만 종료 (VPS용)",
    "default_conditions": ["나의급등주02"],
    "order_type": "03",  # [개선 #3] "03"=시장가, "06"=최유리지정가

    # 계좌는 secrets.json의 mock_target_account / real_target_account를 사용 (config 불필요)

    # 글로벌 기본 매매 파라미터 (조건식별 오버라이드 없으면 이 값 사용)
    "profit": 2.3,
    "loss": -1.7,
    "ts_use": False,
    "ts_activation": 4.0,
    "ts_drop": 0.75,

    # [개선 #18] 조건식별 독립 파라미터 (조건식 이름 → 개별 설정)
    "condition_params": {},

    # [개선 #19] 진입 필터 설정
    "entry_filters": {
        "min_volume": 0,            # 최소 거래량 (0이면 비활성)
        "min_trade_amount": 0,      # 최소 거래대금(원) (0이면 비활성)
        "max_spread_pct": 0,        # 최대 호가 스프레드(%) (0이면 비활성)
        "block_upper_limit": True,  # 상한가 종목 진입 차단
    },
    # [v7.5] 블랙리스트
    "blacklist_enabled": True,
    # [v7.5] 분할 매수 (확인 분할)
    "split_buy_enabled": False,
    "split_buy_rounds": 2,
    "split_buy_ratios": [30, 70],
    "split_buy_confirm_pct": 1.0,
    "split_buy_confirm_pct_3rd": 2.0,
    # [v7.5] 분할 매도 (구간별 고정 익절)
    "split_sell_enabled": False,
    "split_sell_targets": [
        {"pct": 2.0, "ratio": 50},
        {"pct": 4.0, "ratio": 50},
    ],
}


class ConfigManager:
    """봇 설정 로드/저장. 조건식별 파라미터 병합 지원."""

    def __init__(self, config_dir: str):
        self.config_path = os.path.join(config_dir, "bot_config.json")
        self._config = copy.deepcopy(DEFAULT_CONFIG)

    def _deep_merge(self, base: dict, update: dict) -> dict:
        """딕셔너리 내부의 딕셔너리까지 완벽하게 병합 (Deep Merge)"""
        merged = copy.deepcopy(base)
        for k, v in update.items():
            if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                merged[k] = self._deep_merge(merged[k], v)
            else:
                merged[k] = copy.deepcopy(v)
        return merged

    def load(self) -> dict:
        """설정 파일 로드. 없으면 기본값 저장 후 반환."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                
                # 얕은 복사 버그 방지 - 중첩된 딕셔너리까지 안전하게 병합
                self._config = self._deep_merge(DEFAULT_CONFIG, loaded)
            except json.JSONDecodeError as e:
                logger.error(f"❌ [설정] bot_config.json 파싱 실패: {e}. 기본값 사용.")
            except Exception as e:
                logger.error(f"❌ [설정] 설정 로드 실패: {e}. 기본값 사용.")
        else:
            self.save()
            logger.info("✅ [설정] bot_config.json 없음 → 기본 설정 파일 생성.")

        return self._config

    def save(self, config: dict = None):
        """설정 파일 저장."""
        if config:
            self._config = copy.deepcopy(config)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ [설정] 설정 저장 실패: {e}")

    def get(self, key, default=None):
        return self._config.get(key, default)

    def get_condition_param(self, condition_name: str, key: str):
        """
        [개선 #18] 조건식별 파라미터 조회.
        해당 조건식에 개별 설정이 있으면 그 값을, 없으면 글로벌 값을 반환.
        """
        cond_params = self._config.get("condition_params", {})
        if condition_name in cond_params and key in cond_params[condition_name]:
            return cond_params[condition_name][key]
        return self._config.get(key)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        # [Fix #8] 외부에서 불완전한 config dict가 들어와도 DEFAULT_CONFIG 기준으로 누락 키 보정
        self._config = self._deep_merge(DEFAULT_CONFIG, value)