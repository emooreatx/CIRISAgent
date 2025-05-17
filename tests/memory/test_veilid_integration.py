import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open, MagicMock
import asyncio
import json
import base64
import os
import hmac
import hashlib
from pathlib import Path

# Functions/classes to test from veilid_utils.py
from ciris_engine.memory.veilid_utils import do_keygen, do_handshake, do_register
from ciris_engine.memory.veilid_utils import Role as VeilidUtilsRole

# Functions/classes to test from veilid_provider.py
from ciris_engine.memory.veilid_provider import (
    VeilidAgentCore,
    VeilidActHandler,
    VeilidDeferHandler,
    VeilidMemoryHandler,
    Envelope,
    SpeakMessage as ProviderSpeakMessage, 
    DeferralPackage as ProviderDeferralPackage,
    MemoryOperation as ProviderMemoryOperation
)

# Import the module itself to allow mocker.patch.object to work correctly
from ciris_engine.memory import veilid_provider

# Helper to create argparse Namespace
class ArgsNamespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

# --- Fixtures ---

@pytest.fixture
def mock_veilid_api(mocker):
    """
    Provides a comprehensive mock for the 'veilid' module and its interactions
    as used by veilid_utils.py and veilid_provider.py.
    """
    _mock_veilid_module = mocker.MagicMock(name="PatchedVeilidModule_MagicMock")

    # Mock veilid.CryptoKind
    MockCryptoKind = mocker.MagicMock(name="MockCryptoKind")
    MockCryptoKind.CRYPTO_KIND_VLD0 = "mock_crypto_kind_vld0"
    _mock_veilid_module.CryptoKind = MockCryptoKind

    # 1. Mock for the Keypair object and its methods
    explicit_keypair_mock = mocker.MagicMock(name="ExplicitKeypairInstance_MagicMock")
    explicit_keypair_mock.key = mocker.AsyncMock(return_value="mock_public_key_str_from_keypair")
    explicit_keypair_mock.secret = mocker.AsyncMock(return_value="mock_secret_str_from_keypair")

    # Mock for SharedSecret object and its to_bytes method
    shared_secret_mock = mocker.AsyncMock(name="SharedSecret_AsyncMock")
    shared_secret_mock.to_bytes = mocker.AsyncMock(return_value=b"mock_shared_secret_bytes")

    # Mock for veilid_provider.py where self.secret.to_bytes is synchronous
    shared_secret_mock_for_provider = mocker.MagicMock(name="SharedSecret_SyncMock_For_Provider")
    shared_secret_mock_for_provider.to_bytes = mocker.MagicMock(return_value=b"mock_shared_secret_bytes_for_provider_hmac")
    _mock_veilid_module.SharedSecret.from_bytes = mocker.MagicMock(return_value=shared_secret_mock_for_provider)

    # 2. Mock for the Crypto system (async context manager)
    crypto_mock = mocker.AsyncMock(name="CryptoContextManager_AsyncMock")
    crypto_mock.__aenter__.return_value = crypto_mock
    crypto_mock.__aexit__ = mocker.AsyncMock(return_value=None)
    crypto_mock.generate_key_pair = mocker.AsyncMock(return_value=explicit_keypair_mock)
    crypto_mock.cached_dh = mocker.AsyncMock(return_value=shared_secret_mock)

    # 3. Mock for the API connection (async context manager) - used by veilid_utils.py
    conn_mock_for_utils = mocker.AsyncMock(name="APIConnection_ForUtils_AsyncMock")
    conn_mock_for_utils.__aenter__.return_value = conn_mock_for_utils
    conn_mock_for_utils.__aexit__ = mocker.AsyncMock(return_value=None)
    conn_mock_for_utils.get_crypto_system = mocker.AsyncMock(return_value=crypto_mock)
    mock_router_for_utils = mocker.AsyncMock(name="Router_ForUtils_AsyncMock")
    mock_routing_context_for_utils = mocker.AsyncMock(name="RoutingContext_ForUtils_AsyncMock")
    mock_routing_context_for_utils.with_default_safety = mocker.AsyncMock(return_value=mock_router_for_utils)
    conn_mock_for_utils.new_routing_context = mocker.AsyncMock(return_value=mock_routing_context_for_utils)

    # 4. Configure veilid.API (for veilid_utils.py)
    _mock_veilid_module.API = mocker.AsyncMock(return_value=conn_mock_for_utils)

    # --- Mocks for veilid_provider.py ---
    router_mock_for_provider = mocker.AsyncMock(name="Router_ForProvider_AsyncMock")
    router_mock_for_provider.close = mocker.AsyncMock()

    routing_context_mock_for_provider = mocker.AsyncMock(name="RoutingContext_ForProvider_AsyncMock")
    routing_context_mock_for_provider.with_default_safety = mocker.AsyncMock(return_value=router_mock_for_provider)

    conn_mock_for_provider = mocker.AsyncMock(name="APIConnection_ForProvider_AsyncMock")
    conn_mock_for_provider.new_routing_context = mocker.AsyncMock(return_value=routing_context_mock_for_provider)
    conn_mock_for_provider.get_crypto_system = mocker.AsyncMock(return_value=crypto_mock)
    conn_mock_for_provider.close = mocker.AsyncMock()

    _mock_veilid_module.api_connector = mocker.AsyncMock(return_value=conn_mock_for_provider)

    # Mock for veilid.uuid4() used in provider
    _mock_veilid_module.uuid4 = mocker.MagicMock(return_value="mock-uuid-1234")

    # Ensure other necessary mocks for provider are in place
    mock_api_conn = mocker.AsyncMock(name="VeilidAPI_AsyncMock_for_Core")
    mock_routing_context = mocker.AsyncMock(name="RoutingContext_AsyncMock_for_Core")
    mock_routing_context.with_default_safety = mocker.AsyncMock(return_value=mock_routing_context)
    mock_routing_context.set_dht_value = mocker.AsyncMock()
    mock_routing_context.get_dht_value = mocker.AsyncMock(return_value=mocker.MagicMock(data=b'123456789012345678901234' + b'encrypted_payload_here'))
    mock_routing_context.close = mocker.AsyncMock()

    mock_api_conn.new_routing_context = mocker.AsyncMock(return_value=mock_routing_context)

    core_crypto_mock = mocker.AsyncMock(name="CryptoSystem_AsyncMock_for_Core")
    core_crypto_mock.random_nonce = mocker.AsyncMock(return_value=mocker.MagicMock(to_bytes=mocker.MagicMock(return_value=b"mock_nonce_bytes_123456789012345678901234")))
    core_crypto_mock.crypt_no_auth = mocker.AsyncMock(return_value=b"mock_crypted_payload")

    mock_api_conn.get_crypto_system = mocker.AsyncMock(return_value=core_crypto_mock)
    mock_api_conn.close = mocker.AsyncMock()

    _mock_veilid_module.api_connector = mocker.AsyncMock(return_value=mock_api_conn)

    _mock_veilid_module.Keypair = mocker.MagicMock()
    _mock_veilid_module.PublicKey = mocker.MagicMock()
    _mock_veilid_module.Secret = mocker.MagicMock()
    _mock_veilid_module.TypedKey.from_str = mocker.MagicMock(return_value=mocker.MagicMock(name="TypedKey_from_str_mock"))
    _mock_veilid_module.ValueSubkey = mocker.MagicMock()
    _mock_veilid_module.Nonce.from_bytes = mocker.MagicMock(return_value=mocker.MagicMock(name="Nonce_from_bytes_mock"))

    return _mock_veilid_module

@pytest.fixture
def mock_files(mocker):
    mock_home_path = Path("/mock/home/user")
    mocker.patch('pathlib.Path.home', return_value=mock_home_path)
    
    mock_keystore_path_instance = mocker.MagicMock(spec=Path, name="MockedKeyStorePath")
    mock_secretstore_path_instance = mocker.MagicMock(spec=Path, name="MockedSecretStorePath")

    mocker.patch('ciris_engine.memory.veilid_utils.KEYSTORE', mock_keystore_path_instance)
    mocker.patch('ciris_engine.memory.veilid_utils.SECRETSTORE', mock_secretstore_path_instance)
    mocker.patch('ciris_engine.memory.veilid_provider.KEYSTORE', mock_keystore_path_instance)
    mocker.patch('ciris_engine.memory.veilid_provider.SECRETSTORE', mock_secretstore_path_instance)
    
    mock_keystore_path_instance.exists = Mock(return_value=False)
    mock_keystore_path_instance.read_text = Mock(return_value="{}") # Default to empty JSON string
    mock_keystore_path_instance.write_text = Mock()

    mock_secretstore_path_instance.exists = Mock(return_value=False)
    mock_secretstore_path_instance.read_text = Mock(return_value="{}") # Default to empty JSON string
    mock_secretstore_path_instance.write_text = Mock()
    
    return {
        "keystore": mock_keystore_path_instance,
        "secretstore": mock_secretstore_path_instance
    }

@pytest.fixture
def mock_env_vars(mocker):
    env = {
        "VLD_WA_PUBKEY": "env_wa_public_key_str",
        "VLD_AGENT_RECORD_KEY": "env_agent_record_key_str::1",
        "VLD_RECV_MAX_PER_MIN": "60"
    }
    return mocker.patch.dict(os.environ, env, clear=True)

@pytest.fixture
def core_for_provider_tests(mock_files, mock_veilid_api, mock_env_vars, mocker):
    mocker.patch('ciris_engine.memory.veilid_provider.veilid', mock_veilid_api)

    mock_files["keystore"].exists.return_value = True
    keystore_data = {"public_key": "agent_pk_for_provider", "secret": "agent_sk_for_provider"}
    mock_files["keystore"].read_text = Mock(return_value=json.dumps(keystore_data))
    
    mock_files["secretstore"].exists.return_value = True
    wa_pub_key_from_env = mock_env_vars["VLD_WA_PUBKEY"]
    shared_secret_b64 = base64.b64encode(b"a_very_shared_secret").decode()
    secretstore_data = {wa_pub_key_from_env: shared_secret_b64}
    mock_files["secretstore"].read_text = Mock(return_value=json.dumps(secretstore_data))
    mock_veilid_api.SharedSecret.from_bytes.return_value.to_bytes.return_value = b"a_very_shared_secret"

    mocker.patch.object(veilid_provider, 'SpeakMessage', mocker.MagicMock(name="MockSpeakMessage"))
    mocker.patch.object(veilid_provider, 'Observation', mocker.MagicMock(name="MockObservation"))
    mocker.patch.object(veilid_provider, 'DeferralPackage', mocker.MagicMock(name="MockDeferralPackage"))
    mocker.patch.object(veilid_provider, 'AgentCorrectionThought', mocker.MagicMock(name="MockAgentCorrectionThought"))
    mocker.patch.object(veilid_provider, 'MemoryOperation', mocker.MagicMock(name="MockMemoryOperation"))
    
    mocker.patch.object(veilid_provider, 'handle_observe', AsyncMock(name="mock_handle_observe"))
    mocker.patch.object(veilid_provider, 'handle_correction', AsyncMock(name="mock_handle_correction"))

    core = VeilidAgentCore()
    return core


# --- Tests for veilid_utils.py ---

@pytest.mark.asyncio
async def test_do_keygen(mock_files, mock_veilid_api, mocker):
    mocker.patch('ciris_engine.memory.veilid_utils.veilid', mock_veilid_api)

    args = ArgsNamespace()
    await do_keygen(args)

    # Assert that veilid.API() was called and entered
    mock_veilid_api.API.assert_called_once()
    conn_instance = mock_veilid_api.API.return_value.__aenter__.return_value

    # Assert that conn.get_crypto_system was called
    conn_instance.get_crypto_system.assert_called_once_with(mock_veilid_api.CryptoKind.CRYPTO_KIND_VLD0)
    crypto_system_ctx_mgr = conn_instance.get_crypto_system.return_value

    # Assert that the crypto_system_ctx_mgr was entered and generate_key_pair was called on its result
    crypto_system_ctx_mgr.__aenter__.assert_awaited_once()
    crypto_instance = crypto_system_ctx_mgr.__aenter__.return_value
    crypto_instance.generate_key_pair.assert_awaited_once()

    expected_data = {
        "public_key": "mock_public_key_str_from_keypair",
        "secret": "mock_secret_str_from_keypair"
    }
    mock_files["keystore"].write_text.assert_called_once_with(json.dumps(expected_data))

@pytest.mark.asyncio
async def test_do_handshake_with_wa_key(mock_files, mock_veilid_api, mocker):
    mocker.patch('ciris_engine.memory.veilid_utils.veilid', mock_veilid_api)
    conn_instance = mock_veilid_api.API.return_value.__aenter__.return_value
    conn_instance.get_crypto_system.return_value = conn_instance.get_crypto_system.return_value.__aenter__.return_value 

    keystore_content = {"public_key": "my_agent_pub_key", "secret": "my_agent_secret"}
    mock_files["keystore"].exists.return_value = True
    mock_files["keystore"].read_text = Mock(return_value=json.dumps(keystore_content))
    mock_files["secretstore"].exists.return_value = False 

    args = ArgsNamespace(wa_key="provided_wa_key_str")
    await do_handshake(args)

    crypto_instance = conn_instance.get_crypto_system.return_value
    
    mock_veilid_api.PublicKey.from_string.assert_any_call("my_agent_pub_key")
    mock_veilid_api.PublicKey.from_string.assert_any_call("provided_wa_key_str")
    mock_veilid_api.SecretKey.from_string.assert_any_call("my_agent_secret")

    crypto_instance.cached_dh.assert_called_once()
    
    shared_secret_bytes = crypto_instance.cached_dh.return_value.to_bytes.return_value
    expected_secret_b64 = base64.b64encode(shared_secret_bytes).decode()
    expected_secretstore_data = {"provided_wa_key_str": expected_secret_b64}
    mock_files["secretstore"].write_text.assert_called_once_with(json.dumps(expected_secretstore_data))

@pytest.mark.asyncio
async def test_do_handshake_discover_wa(mock_files, mock_veilid_api, mocker):
    mocker.patch('ciris_engine.memory.veilid_utils.veilid', mock_veilid_api)
    conn_instance = mock_veilid_api.API.return_value.__aenter__.return_value
    conn_instance.get_crypto_system.return_value = conn_instance.get_crypto_system.return_value.__aenter__.return_value

    mock_list_profiles = AsyncMock(return_value=[{"public_key": "discovered_wa_key_str"}])
    mocker.patch('ciris_engine.memory.veilid_utils.list_profiles', mock_list_profiles)

    keystore_content = {"public_key": "my_agent_pub_key", "secret": "my_agent_secret"}
    mock_files["keystore"].exists.return_value = True
    mock_files["keystore"].read_text = Mock(return_value=json.dumps(keystore_content))

    args = ArgsNamespace(wa_key=None) 
    await do_handshake(args)

    mock_list_profiles.assert_called_once()
    mock_veilid_api.PublicKey.from_string.assert_any_call("discovered_wa_key_str")

@pytest.mark.asyncio
async def test_do_register(mock_files, mock_veilid_api, mocker):
    mocker.patch('ciris_engine.memory.veilid_utils.veilid', mock_veilid_api)
    mock_advertise_profile = AsyncMock()
    mocker.patch('ciris_engine.memory.veilid_utils.advertise_profile', mock_advertise_profile)

    keystore_content = {"public_key": "my_agent_public_key_for_reg"}
    mock_files["keystore"].exists.return_value = True
    mock_files["keystore"].read_text = Mock(return_value=json.dumps(keystore_content))

    args = ArgsNamespace(name="MyRegisteredAgent")
    await do_register(args)

    conn_instance = mock_veilid_api.API.return_value.__aenter__.return_value
    router_instance = conn_instance.new_routing_context.return_value.with_default_safety.return_value
    
    expected_profile = {"name": "MyRegisteredAgent", "public_key": "my_agent_public_key_for_reg"}
    mock_advertise_profile.assert_called_once_with(
        router_instance,
        VeilidUtilsRole.AGENT,
        expected_profile
    )

# --- Tests for veilid_provider.py ---

@pytest.mark.asyncio
async def test_veilid_agent_core_start_success(core_for_provider_tests, mock_veilid_api, mock_env_vars):
    core = core_for_provider_tests
    await core.start()

    mock_veilid_api.api_connector.assert_called_once()
    assert core.conn is not None
    assert core.router is not None
    assert core.crypto is not None
    
    mock_veilid_api.Keypair.assert_called_once()
    pub_key_arg = mock_veilid_api.Keypair.call_args[0][0]
    sec_key_arg = mock_veilid_api.Keypair.call_args[0][1]
    assert isinstance(pub_key_arg, type(mock_veilid_api.PublicKey.return_value))
    assert isinstance(sec_key_arg, type(mock_veilid_api.Secret.return_value))
    
    mock_veilid_api.PublicKey.assert_any_call("agent_pk_for_provider") 
    mock_veilid_api.Secret.assert_any_call("agent_sk_for_provider")   
    mock_veilid_api.PublicKey.assert_any_call(mock_env_vars["VLD_WA_PUBKEY"]) 

    mock_veilid_api.SharedSecret.from_bytes.assert_called_once_with(b"a_very_shared_secret")
    mock_veilid_api.TypedKey.from_str.assert_called_once_with(mock_env_vars["VLD_AGENT_RECORD_KEY"])
    
    assert core.running is True

@pytest.mark.asyncio
async def test_veilid_agent_core_stop(core_for_provider_tests, mock_veilid_api):
    core = core_for_provider_tests
    await core.start() 
    
    router_close_mock = core.router.close
    conn_close_mock = core.conn.close

    await core.stop()

    router_close_mock.assert_awaited_once()
    conn_close_mock.assert_awaited_once()
    assert core.running is False

@pytest.mark.asyncio
async def test_veilid_agent_core_send(core_for_provider_tests, mock_veilid_api):
    core = core_for_provider_tests
    await core.start()
    # Reset the mock for random_nonce after core.start() has called it once
    core.crypto.random_nonce.reset_mock() 
    
    op_type = "TEST_SEND_OP"
    body_data = {"message": "greetings"}
    subkey_val = 0

    await core._send(op_type, body_data, subkey_val)

    mock_veilid_api.uuid4.assert_called_once()
    eid = mock_veilid_api.uuid4.return_value
    
    core.crypto.random_nonce.assert_awaited_once()
    nonce_instance = core.crypto.random_nonce.return_value
    
    encrypt_call = core.crypto.crypt_no_auth.call_args_list[0] 
    clear_bytes_arg = encrypt_call[0][0]
    nonce_arg = encrypt_call[0][1]
    
    assert nonce_arg == nonce_instance
    
    clear_dict_arg = json.loads(clear_bytes_arg.decode())
    assert clear_dict_arg["id"] == eid
    assert clear_dict_arg["op"] == op_type
    assert clear_dict_arg["body"] == body_data
    assert "hmac" in clear_dict_arg 

    expected_dht_payload = nonce_instance.to_bytes.return_value + core.crypto.crypt_no_auth.return_value
    core.router.set_dht_value.assert_awaited_once_with(
        core.record_key,
        mock_veilid_api.ValueSubkey.return_value, 
        expected_dht_payload
    )
    mock_veilid_api.ValueSubkey.assert_called_with(subkey_val)

@pytest.mark.asyncio
async def test_veilid_agent_core_recv_success(core_for_provider_tests, mock_veilid_api, mocker):
    core = core_for_provider_tests
    await core.start()
    mocker.patch('hmac.compare_digest', return_value=True) 

    subkey_to_get = 1
    
    expected_id = "recv-msg-id"
    expected_op = "FROM_WA_OP"
    expected_body = {"data": "from_wa_payload"}
    dummy_hmac_in_payload = base64.b64encode(b"valid_looking_hmac").decode()

    decrypted_payload_str = json.dumps({
        "id": expected_id, "op": expected_op, "body": expected_body, "hmac": dummy_hmac_in_payload
    })
    core.crypto.crypt_no_auth.return_value = decrypted_payload_str.encode()


    envelope = await core._recv(subkey_to_get)

    core.router.get_dht_value.assert_awaited_once_with(
        core.record_key, mock_veilid_api.ValueSubkey.return_value, True
    )
    mock_veilid_api.ValueSubkey.assert_called_with(subkey_to_get)
    
    dht_data = core.router.get_dht_value.return_value.data
    nonce_bytes_from_dht = dht_data[:24] 
    cipher_bytes_from_dht = dht_data[24:]
    mock_veilid_api.Nonce.from_bytes.assert_called_once_with(nonce_bytes_from_dht)
    
    core.crypto.crypt_no_auth.assert_called_once_with(
        cipher_bytes_from_dht,
        mock_veilid_api.Nonce.from_bytes.return_value, 
        core.secret
    )
    
    assert envelope is not None
    assert envelope.id == expected_id
    assert envelope.op == expected_op
    assert envelope.body == expected_body

@pytest.mark.asyncio
async def test_act_handler_speak(core_for_provider_tests, mocker):
    core = core_for_provider_tests
    await core.start()
    act_handler = VeilidActHandler(core)

    core._send = AsyncMock() 

    mock_msg_payload = {"text_content": "A message to speak"}
    mock_speak_msg_instance = mocker.MagicMock() 
    
    mocked_vars = mocker.patch('ciris_engine.memory.veilid_provider.vars', return_value=mock_msg_payload) 

    await act_handler.speak(mock_speak_msg_instance)

    core._send.assert_awaited_once_with("SPEAK", mock_msg_payload, subkey=0)
    mocked_vars.assert_called_once_with(mock_speak_msg_instance)

@pytest.mark.asyncio
async def test_act_handler_start_observe_receives_and_handles_message(core_for_provider_tests, mocker):
    core = core_for_provider_tests
    await core.start()
    act_handler = VeilidActHandler(core)

    observe_payload = {"observer_name": "test_observer", "detail": "something happened"}
    observe_envelope = Envelope(id="obs1", op="OBSERVE", body=observe_payload, hmac_sig="dummy")

    side_effect_state = {"call_count": 0}
    async def recv_side_effect(subkey):
        if subkey == 1 and core.running: 
            if side_effect_state["call_count"] == 0:
                side_effect_state["call_count"] += 1
                return observe_envelope
        core.running = False 
        return None
    core._recv = AsyncMock(side_effect=recv_side_effect)

    MockObservationClass_patched = mocker.patch.object(veilid_provider, 'Observation')
    mock_handle_observe_func = mocker.patch.object(veilid_provider, 'handle_observe', new_callable=AsyncMock)

    await act_handler.start_observe()

    core._recv.assert_any_call(subkey=1) 
    MockObservationClass_patched.assert_called_once_with(**observe_payload)
    mock_handle_observe_func.assert_awaited_once_with(MockObservationClass_patched.return_value)

# --- Placeholder for DeferHandler and MemoryHandler tests ---

@pytest.mark.asyncio
async def test_defer_handler_defer(core_for_provider_tests, mocker):
    core = core_for_provider_tests
    await core.start()
    defer_handler = VeilidDeferHandler(core)
    core._send = AsyncMock()

    mock_pkg_payload = {"ticket_id": "defer123", "reason": "busy"}
    mock_deferral_pkg_instance = mocker.MagicMock()

    mocked_vars = mocker.patch('ciris_engine.memory.veilid_provider.vars', return_value=mock_pkg_payload)

    await defer_handler.defer(mock_deferral_pkg_instance)

    core._send.assert_awaited_once_with("DEFER", mock_pkg_payload, subkey=0)
    mocked_vars.assert_called_once_with(mock_deferral_pkg_instance)

@pytest.mark.asyncio
async def test_defer_handler_start_correction_receives_message(core_for_provider_tests, mocker):
    core = core_for_provider_tests
    await core.start()
    defer_handler = VeilidDeferHandler(core)

    correction_payload = {"correction_id": "corr789", "suggestion": "try again"}
    correction_envelope = Envelope(id="corr1", op="CORRECTION", body=correction_payload, hmac_sig="dummy_hmac")

    side_effect_state_correction = {"call_count": 0}
    async def recv_side_effect_correction(subkey):
        if subkey == 1 and core.running:
            if side_effect_state_correction["call_count"] == 0:
                side_effect_state_correction["call_count"] += 1
                return correction_envelope
        core.running = False
        return None
    core._recv = AsyncMock(side_effect=recv_side_effect_correction)
    
    MockAgentCorrectionThoughtClass_patched = mocker.patch.object(veilid_provider, 'AgentCorrectionThought')
    mock_handle_correction_func = mocker.patch.object(veilid_provider, 'handle_correction', new_callable=AsyncMock)

    await defer_handler.start_correction()

    core._recv.assert_any_call(subkey=1)
    MockAgentCorrectionThoughtClass_patched.assert_called_once_with(**correction_payload)
    mock_handle_correction_func.assert_awaited_once_with(MockAgentCorrectionThoughtClass_patched.return_value)


@pytest.mark.asyncio
async def test_memory_handler_memory_op(core_for_provider_tests, mocker):
    core = core_for_provider_tests
    await core.start()
    memory_handler = VeilidMemoryHandler(core)
    core._send = AsyncMock()

    mock_mem_op_payload = {"operation": "learn", "data": {"fact": "pytest is cool"}}
    mock_memory_op_instance = mocker.MagicMock()

    mocked_vars = mocker.patch('ciris_engine.memory.veilid_provider.vars', return_value=mock_mem_op_payload)
    
    await memory_handler.memory(mock_memory_op_instance)
    core._send.assert_awaited_once_with("MEMORY", mock_mem_op_payload, subkey=0)
    mocked_vars.assert_called_once_with(mock_memory_op_instance)